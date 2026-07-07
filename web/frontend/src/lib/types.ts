export type DisagMethod = 0 | 1 | 2 | 3 | 4 | 5;

/**
 * Server-side enforced upload contract: a presigned S3 POST policy with
 * content-length-range + content-type conditions. The client POSTs
 * FormData to `url` with `fields` flattened first, then `file` last —
 * S3 rejects the upload server-side if any condition is violated.
 */
export interface UploadTarget {
	key: string;
	url: string;
	fields: Record<string, string>;
	expires_in: number;
	max_bytes: number;
}

export interface DisagRequest {
	method: DisagMethod;
	monthly_key: string;
	daily1_key?: string | null;
	daily2_key?: string | null;
	/**
	 * Method 5 only. When ≥ this fraction (0–1] of a month's days are missing
	 * from file 1, rebuild the whole month from one coherent source instead of
	 * splicing sources day-by-day. Source priority: file 2 if it covers the
	 * whole month, else the exceedance-matched donor. null/omitted = splice.
	 */
	whole_month_donor_fraction?: number | null;
}

export interface SeasonGroup {
	name: string;
	months: number[]; // calendar months 1-12 pooled into this season
}

export interface ExceedRequest {
	monthly_key?: string | null;
	daily_key?: string | null;
	intervals?: number;
	/** Free-form seasonal pooling; omit for per-calendar-month curves. */
	seasons?: SeasonGroup[];
}

export interface ConvertRequest {
	ans_key: string;
}

export type Tool = 'disag' | 'exceed' | 'convert';

export interface RunResult {
	run_id: string;
	tool: Tool;
	created_at: string;
	output_key?: string;
	report_key: string;
	output_url?: string;
	report_url: string;
}

export interface RunSummary {
	run_id: string;
	tool: Tool;
	created_at: string;
	size_bytes: number;
}
