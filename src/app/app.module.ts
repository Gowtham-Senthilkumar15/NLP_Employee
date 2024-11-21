import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';
import { AppRoutingModule } from './app-routing.module'; // Import AppRoutingModule

import { AppComponent } from './app.component';
import { CouchdbService } from './couchdb.service'; // CouchDB service
import { GeminiService } from './home/gemini.service'; // Gemini service
import { HomeComponent } from './home/home.component'; // Home component
import { LoginComponent } from './login/login.component'; // Login component

@NgModule({
  declarations: [
    AppComponent,
    HomeComponent,
    LoginComponent
  ],
  imports: [
    BrowserModule,
    FormsModule,
    HttpClientModule, // For making HTTP requests
    AppRoutingModule // For routing between components
  ],
  providers: [
    CouchdbService, // CouchDB service
    GeminiService   // Gemini service for AI query handling
  ],
  bootstrap: [AppComponent]
})
export class AppModule { }
