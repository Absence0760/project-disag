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
	 * Methods 1, 2 and 5. When ≥ this fraction (0–1] of a month's days are
	 * missing from file 1, rebuild the whole month from one coherent donor
	 * instead of splicing sources day-by-day. The donor is the matched
	 * calendar month (method 1), file 2 (method 2), or file 2 then the
	 * exceedance-matched donor (method 5). null/omitted = splice.
	 */
	whole_month_fraction?: number | null;
	/**
	 * Method 5 only. Map injected file-2/donor day values through the source
	 * file's daily flow-duration curve onto file 1's, instead of the linear
	 * mean-ratio scale factor. false/omitted = linear factor.
	 */
	daily_fdc_mapping?: boolean;
	/**
	 * Method 5 only. Blend each spliced gap run into the observed days at
	 * its edges. Best combined with daily_fdc_mapping. false/omitted = off.
	 */
	seam_blend?: boolean;
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
