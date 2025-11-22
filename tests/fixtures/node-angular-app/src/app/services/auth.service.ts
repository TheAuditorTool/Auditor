/**
 * Auth Service - Authentication with DI and RxJS
 * Tests: @Injectable, BehaviorSubject, local storage, authentication flow
 */

import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, BehaviorSubject } from 'rxjs';
import { map, tap } from 'rxjs/operators';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private currentUserSubject: BehaviorSubject<any>;
  public currentUser$: Observable<any>;
  private tokenKey = 'auth_token';

  constructor(
    private http: HttpClient,
    private router: Router
  ) {
    const storedUser = localStorage.getItem('currentUser');
    this.currentUserSubject = new BehaviorSubject<any>(
      storedUser ? JSON.parse(storedUser) : null
    );
    this.currentUser$ = this.currentUserSubject.asObservable();
  }

  public get currentUserValue(): any {
    return this.currentUserSubject.value;
  }

  public get isAuthenticated(): boolean {
    return !!this.currentUserValue && !!this.getToken();
  }

  /**
   * Login user
   * Tests: POST request with credentials, token storage
   * TAINT FLOW: credentials (user input) -> API -> localStorage
   */
  login(credentials: { email: string; password: string }): Observable<any> {
    return this.http.post<any>('/api/auth/login', credentials).pipe(
      map((response) => {
        if (response && response.token) {
          localStorage.setItem(this.tokenKey, response.token);
          localStorage.setItem('currentUser', JSON.stringify(response.user));
          this.currentUserSubject.next(response.user);
        }
        return response;
      })
    );
  }

  /**
   * Logout user
   * Tests: Clear auth state, navigate to login
   */
  logout(): void {
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem('currentUser');
    this.currentUserSubject.next(null);
    this.router.navigate(['/login']);
  }

  /**
   * Get auth token
   * Tests: Token retrieval from localStorage
   */
  getToken(): string | null {
    return localStorage.getItem(this.tokenKey);
  }

  /**
   * Refresh token
   * Tests: Token refresh flow
   */
  refreshToken(): Observable<any> {
    return this.http.post<any>('/api/auth/refresh', {}).pipe(
      tap((response) => {
        if (response && response.token) {
          localStorage.setItem(this.tokenKey, response.token);
        }
      })
    );
  }
}
