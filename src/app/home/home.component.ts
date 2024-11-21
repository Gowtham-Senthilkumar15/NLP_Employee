import { Component, OnInit, OnDestroy } from '@angular/core';
import { Router } from '@angular/router';
import { GeminiService } from './gemini.service';
import { Subscription } from 'rxjs';

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.css']
})
export class HomeComponent implements OnInit, OnDestroy {
  query: string = ''; // User's query input
  conversation: { 
    query: string; 
    response: string; 
    sources?: { doc_id: string }[]; // Metadata for the sources
    isTyping?: boolean; 
  }[] = []; // Array to hold conversation history
  errorMessage: string | null = null; // Error message display
  isLoading: boolean = false; // Loading state
  private currentRequest?: Subscription; // To track and cancel ongoing requests
  private typingInterval?: any; // Typing interval reference to stop typing

  constructor(private router: Router, private geminiService: GeminiService) {}

  ngOnInit(): void {
    const isAuthenticated = localStorage.getItem('isAuthenticated');
    if (!isAuthenticated) {
      this.router.navigate(['/login']);
    }
  }

  onSearch(searchValue: string): void {
    if (this.isLoading) return; // Prevent new search if one is already loading

    this.query = searchValue.trim();
    if (!this.query) {
      this.errorMessage = 'Enter something to search';
      return;
    }

    this.isLoading = true;
    this.errorMessage = null;

    // Add the user query to the conversation before making the API request
    this.conversation.push({ query: this.query, response: '', isTyping: true });

    // Make the API call and store the subscription to allow cancellation
    this.currentRequest = this.geminiService.queryChromaDB(this.query).subscribe({
      next: (data) => {
        const response = data.answer || 'No result found';
        const sources = data.sources || []; // Extract sources metadata
        const index = this.conversation.length - 1;

        // Start typing effect and store sources
        this.typeResponse(response, index, () => {
          this.conversation[index].sources = sources; // Add metadata after typing
        });

        this.query = ''; // Clear input field after response
        this.errorMessage = null;
      },
      error: (error) => {
        this.errorMessage = 'There was an error processing your request';
        console.error('Error:', error);
      },
      complete: () => {
        this.isLoading = false;
      }
    });
  }

  // Typing effect function with callback
  typeResponse(text: string, index: number, callback?: () => void, delay: number = 2): void {
    let i = 0;
    this.typingInterval = setInterval(() => {
      if (i < text.length) {
        this.conversation[index].response += text.charAt(i);
        i++;
      } else {
        clearInterval(this.typingInterval);
        this.typingInterval = null;
        this.conversation[index].isTyping = false; // End typing effect

        // Execute callback to add metadata or other actions
        if (callback) callback();
      }
    }, delay);
  }

  // Stop button handler to cancel the typing effect only
  onStop(): void {
    if (this.typingInterval) {
      clearInterval(this.typingInterval); // Stop typing interval
      this.typingInterval = null;
      const lastResponseIndex = this.conversation.length - 1;
      if (this.conversation[lastResponseIndex]) {
        this.conversation[lastResponseIndex].isTyping = false; // Stop typing indicator
      }
    }
  }

  ngOnDestroy(): void {
    // Cleanup logic if needed
    if (this.currentRequest) {
      this.currentRequest.unsubscribe();
    }
    if (this.typingInterval) {
      clearInterval(this.typingInterval);
    }
  }
}
