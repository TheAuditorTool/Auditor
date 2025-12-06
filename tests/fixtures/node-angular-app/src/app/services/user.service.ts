import { Injectable } from "@angular/core";
import { HttpClient, HttpParams } from "@angular/common/http";
import { Observable, BehaviorSubject, throwError } from "rxjs";
import { map, catchError, tap, retry, shareReplay } from "rxjs/operators";

import { User, UserFilters } from "../models/user.model";
import { ApiService } from "./api.service";
import { StateService } from "./state.service";

@Injectable({
  providedIn: "root",
})
export class UserService {
  private apiUrl = "/api/users";
  private usersSubject = new BehaviorSubject<User[]>([]);
  public users$ = this.usersSubject.asObservable();

  constructor(
    private http: HttpClient,
    private apiService: ApiService,
    private stateService: StateService,
  ) {}

  getUsers(filters?: UserFilters): Observable<User[]> {
    let params = new HttpParams();

    if (filters) {
      if (filters.status) params = params.set("status", filters.status);
      if (filters.role) params = params.set("role", filters.role);
      if (filters.search) params = params.set("search", filters.search);
    }

    return this.http.get<User[]>(this.apiUrl, { params }).pipe(
      retry(2),
      tap((users) => this.usersSubject.next(users)),
      shareReplay(1),
      catchError(this.handleError),
    );
  }

  getUserById(userId: string): Observable<User> {
    return this.http.get<User>(`${this.apiUrl}/${userId}`).pipe(
      retry(1),
      tap((user) => this.stateService.setCurrentUser(user)),
      catchError(this.handleError),
    );
  }

  createUser(userData: Partial<User>): Observable<User> {
    return this.http.post<User>(this.apiUrl, userData).pipe(
      tap((newUser) => {
        const currentUsers = this.usersSubject.value;
        this.usersSubject.next([...currentUsers, newUser]);
      }),
      catchError(this.handleError),
    );
  }

  updateUser(userId: string, updates: Partial<User>): Observable<User> {
    return this.http.put<User>(`${this.apiUrl}/${userId}`, updates).pipe(
      tap((updatedUser) => {
        const currentUsers = this.usersSubject.value;
        const index = currentUsers.findIndex((u) => u.id === userId);
        if (index !== -1) {
          currentUsers[index] = updatedUser;
          this.usersSubject.next([...currentUsers]);
        }
      }),
      catchError(this.handleError),
    );
  }

  deleteUser(userId: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${userId}`).pipe(
      tap(() => {
        const currentUsers = this.usersSubject.value;
        this.usersSubject.next(currentUsers.filter((u) => u.id !== userId));
      }),
      catchError(this.handleError),
    );
  }

  searchUsers(searchQuery: string): Observable<User[]> {
    const params = new HttpParams().set("q", searchQuery);

    return this.http.get<User[]>(`${this.apiUrl}/search`, { params }).pipe(
      map((users) => users.filter((u) => u.status === "active")),
      catchError(this.handleError),
    );
  }

  getUserStats(userId: string): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/${userId}/stats`).pipe(
      map((stats) => ({
        ...stats,
        lastActive: new Date(stats.lastActive),
        joinedDate: new Date(stats.joinedDate),
      })),
      catchError(this.handleError),
    );
  }

  bulkUpdateUsers(userIds: string[], updates: Partial<User>): Observable<any> {
    return this.http
      .post(`${this.apiUrl}/bulk-update`, { userIds, updates })
      .pipe(
        tap(() => this.refreshUsers()),
        catchError(this.handleError),
      );
  }

  private refreshUsers(): void {
    this.getUsers().subscribe();
  }

  private handleError(error: any): Observable<never> {
    console.error("UserService error:", error);
    return throwError(() => new Error(error.message || "Server error"));
  }
}
