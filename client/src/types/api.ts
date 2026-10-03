export type ContentType = "text" | "image";
export type Action = "MASK" | "REMOVE" | "KEEP";
export type RiskScore = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
export type PIIType = "AADHAAR" | "PAN" | "PHONE" | "BANK_ACCOUNT" | "IFSC" | "UPI" | "CREDIT_CARD";

export interface BoundingBox { x: number; y: number; w: number; h: number }
export interface DetectedItem {
  id: string; type: PIIType; raw_value: string; value_masked: string;
  is_valid: boolean; validation_method: string; validation_reason: string;
  confidence: number; start: number | null; end: number | null;
  bounding_box: BoundingBox | null; action: Action;
}
export interface AnalyzeSummary { total_pii_found: number; validated_pii_count: number; risk_score: RiskScore; breakdown: Record<string, number> }
export interface AnalyzeResponse { status: "success"; request_id: string; content_type: ContentType; extracted_text: string | null; detected_items: DetectedItem[]; summary: AnalyzeSummary; warnings: string[] }
export interface RedactionRule { id: string; action: Action }
export interface RedactRequest { request_id: string; content_type: ContentType; text?: string | null; file_b64?: string | null; detected_items: DetectedItem[]; redaction_rules: RedactionRule[] }
export interface ProtectionSummary { protected_records_count: number; breakdown: Record<string, number>; status: "SECURED" }
export interface RedactResponse { status: "success"; sanitized_text: string | null; sanitized_file_b64: string | null; download_filename: string; protection_summary: ProtectionSummary }
