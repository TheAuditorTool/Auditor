import { Injectable } from '@angular/core';
import {
  HttpRequest,
  HttpHandler,
  HttpEvent,
  HttpInterceptor,
  HttpErrorResponse,
  HttpResponse
} from '@angular/common/http';
import { Observable, throwError, BehaviorSubject, of } from 'rxjs';
import {
  catchError,
  filter,
  take,
  switchMap,
  tap,
  retry,
  retryWhen,
  delay,
  mergeMap,
  finalize,
  timeout
} from 'rxjs/operators';
import { AuthService } from '../services/auth.service';
import { TokenService } from '../services/token.service';
import { Router } from '@angular/router';

@Injectable()
export class AuthInterceptor implements HttpInterceptor {
  private isRefreshing = false;
  private refreshTokenSubject: BehaviorSubject<any> = new BehaviorSubject<any>(null);
  private requestQueue = new Map<string, Observable<HttpEvent<any>>>();

  constructor(
    private authService: AuthService,
    private tokenService: TokenService,
    private router: Router
  ) {}

  intercept(request: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    // Skip interceptor for auth endpoints
    if (this.isAuthEndpoint(request.url)) {
      return next.handle(request);
    }

    // Add auth header
    let authReq = request;
    const token = this.tokenService.getAccessToken();

    if (token) {
      authReq = this.addToken(request, token);
    }

    // Add request tracking
    const requestId = this.generateRequestId();
    authReq = authReq.clone({
      headers: authReq.headers.set('X-Request-Id', requestId)
    });

    // Handle request with retry logic and token refresh
    return next.handle(authReq).pipe(
      timeout(30000), // 30 second timeout
      tap((event: HttpEvent<any>) => {
        if (event instanceof HttpResponse) {
          // Log successful responses
          this.logResponse(requestId, event);
        }
      }),
      retryWhen(errors =>
        errors.pipe(
          mergeMap((error, index) => {
            // Retry logic with exponential backoff
            if (index < 3 && this.shouldRetry(error)) {
              const backoffTime = Math.pow(2, index) * 1000;
              return of(error).pipe(delay(backoffTime));
            }
            return throwError(error);
          })
        )
      ),
      catchError(error => {
        if (error instanceof HttpErrorResponse) {
          switch (error.status) {
            case 401:
              return this.handle401Error(authReq, next);
            case 403:
              return this.handle403Error(error);
            case 429:
              return this.handle429Error(authReq, next);
            case 500:
            case 502:
            case 503:
            case 504:
              return this.handleServerError(error);
            default:
              return throwError(error);
          }
        }
        return throwError(error);
      }),
      finalize(() => {
        // Clean up request tracking
        this.requestQueue.delete(requestId);
      })
    );
  }

  private handle401Error(request: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    if (!this.isRefreshing) {
      this.isRefreshing = true;
      this.refreshTokenSubject.next(null);

      return this.authService.refreshToken().pipe(
        switchMap((token: any) => {
          this.isRefreshing = false;
          this.refreshTokenSubject.next(token.accessToken);
          return next.handle(this.addToken(request, token.accessToken));
        }),
        catchError(err => {
          this.isRefreshing = false;
          this.authService.logout();
          this.router.navigate(['/login']);
          return throwError(err);
        })
      );
    } else {
      // Wait for token refresh to complete
      return this.refreshTokenSubject.pipe(
        filter(token => token != null),
        take(1),
        switchMap(token => {
          return next.handle(this.addToken(request, token));
        })
      );
    }
  }

  private handle403Error(error: HttpErrorResponse): Observable<never> {
    // Handle forbidden access
    this.router.navigate(['/access-denied'], {
      queryParams: {
        resource: error.url,
        reason: error.error?.message || 'Insufficient permissions'
      }
    });
    return throwError(error);
  }

  private handle429Error(request: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    // Rate limiting - wait and retry
    const retryAfter = this.getRetryAfter(request.headers);
    return of(null).pipe(
      delay(retryAfter * 1000),
      switchMap(() => next.handle(request))
    );
  }

  private handleServerError(error: HttpErrorResponse): Observable<never> {
    // Log server errors for monitoring
    console.error('Server error:', {
      status: error.status,
      message: error.message,
      url: error.url,
      timestamp: new Date().toISOString()
    });

    // Navigate to error page for persistent errors
    if (error.status === 503) {
      this.router.navigate(['/maintenance']);
    }

    return throwError(error);
  }

  private addToken(request: HttpRequest<any>, token: string): HttpRequest<any> {
    return request.clone({
      setHeaders: {
        Authorization: `Bearer ${token}`
      }
    });
  }

  private isAuthEndpoint(url: string): boolean {
    const authEndpoints = ['/auth/login', '/auth/refresh', '/auth/logout', '/auth/register'];
    return authEndpoints.some(endpoint => url.includes(endpoint));
  }

  private shouldRetry(error: any): boolean {
    // Retry on network errors or specific status codes
    return !error.status || [408, 429, 500, 502, 503, 504].includes(error.status);
  }

  private generateRequestId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  private getRetryAfter(headers: any): number {
    const retryAfter = headers.get('Retry-After');
    return retryAfter ? parseInt(retryAfter, 10) : 5;
  }

  private logResponse(requestId: string, response: HttpResponse<any>): void {
    // Performance tracking
    const timing = performance.getEntriesByName(requestId)[0];
    if (timing) {
      console.log('Request performance:', {
        id: requestId,
        duration: timing.duration,
        status: response.status
      });
    }
  }
}