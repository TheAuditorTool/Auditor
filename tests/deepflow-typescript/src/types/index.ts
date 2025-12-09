/**
 * Type definitions for DeepFlow TypeScript.
 */

export interface ApiResponse<T = any> {
  result: T;
  error?: string;
  count?: number;
}

export interface SearchQuery {
  q: string; // TAINTED - SQL Injection vector
}

export interface FilterQuery {
  filter: any; // TAINTED - NoSQL Injection vector
}

export interface ReportGenerateDTO {
  title: string; // TAINTED - XSS vector
  data: any;
}

export interface SettingsUpdateDTO {
  settings: any; // TAINTED - Prototype Pollution vector
}
