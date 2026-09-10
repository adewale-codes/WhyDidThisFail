export interface ErrorSignal {
  format: string;
  error_type: string | null;
  message: string;
  file: string | null;
  line: number | null;
  context: string;
  extra: Record<string, unknown>;
}

export interface DiagnoseResponse {
  detected_format: string;
  error_signal: ErrorSignal;
  cause: string;
  explanation: string;
  fix: string;
  commands: string[];
  source: "pattern" | "llm";
  pattern_id: string | null;
}

export interface StoredResult {
  id: string;
  createdAt: string;
  sanitizedLog: string;
  redactionCount: number;
  result: DiagnoseResponse;
}
