import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError, map } from 'rxjs/operators';

@Injectable({
  providedIn: 'root',
})
export class GeminiService {
  private apiUrl = 'http://localhost:8000/query/'; // FastAPI backend URL

  constructor(private http: HttpClient) {}

  // Function to send a query to the FastAPI backend and receive results, including metadata
  queryChromaDB(userQuery: string): Observable<any> {
    const headers = new HttpHeaders({ 'Content-Type': 'application/json' });
    const body = { query: userQuery }; // Request payload matching FastAPI model

    return this.http.post<any>(this.apiUrl, body, { headers }).pipe(
      map((response) => {
        // Parse the response to separate answer and metadata
        return {
          query: response.query,
          answer: response.answer,
          sources: response.sources, // Metadata with doc_id
          conversation: response.conversation,
        };
      }),
      catchError(this.handleError) // Error handling
    );
  }

  // Error handling function
  private handleError(error: HttpErrorResponse): Observable<never> {
    if (error.error instanceof ErrorEvent) {
      // A client-side or network error occurred
      console.error('A client-side or network error occurred:', error.error.message);
    } else {
      // The backend returned an unsuccessful response code
      console.error(
        `Backend returned code ${error.status}, ` +
        `body was: ${error.error}`
      );
    }
    // Return a user-friendly error message
    return throwError(() => new Error('API call failed, please try again.'));
  }
}
