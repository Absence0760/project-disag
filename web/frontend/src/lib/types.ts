export type DisagMethod = 0 | 1 | 2 | 3 | 4 | 5;

export interface UploadTarget {
	key: string;
	url: string;
	expires_in: number;
}

export interface DisagRequest {
	method: DisagMethod;
	monthly_key: string;
	daily1_key?: string | null;
	daily2_key?: string | null;
}

export interface ExceedRequest {
	monthly_key?: string | null;
	daily_key?: string | null;
	intervals?: number;
}

export interface RunResult {
	run_id: string;
	tool: 'disag' | 'exceed';
	created_at: string;
	output_key?: string;
	report_key: string;
	output_url?: string;
	report_url: string;
}

export interface RunSummary {
	run_id: string;
	tool: 'disag' | 'exceed';
	created_at: string;
	size_bytes: number;
}
