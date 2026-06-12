// Small formatting helpers shared by the run, run/[run_id], and history
// routes so the same artifact reads the same way on every page.

/** Human label for a download, special-casing the exceed SVG curve. */
export function outputLabel(key: string | undefined): string {
	if (!key) return 'output';
	const m = key.match(/\.([a-z0-9]+)$/i);
	if (m && m[1].toLowerCase() === 'svg') return 'curve (.svg)';
	return m ? `.${m[1].toLowerCase()} output` : 'output';
}

/** True when a stored output is the exceed SVG curve (so it can be previewed). */
export function isSvgOutput(key: string | undefined): boolean {
	return !!key && /\.svg$/i.test(key);
}

/** Locale date/time with an explicit zone, so timestamps aren't ambiguous. */
export function fmtDateTime(iso: string): string {
	return new Date(iso).toLocaleString(undefined, {
		year: 'numeric',
		month: 'short',
		day: '2-digit',
		hour: '2-digit',
		minute: '2-digit',
		timeZoneName: 'short'
	});
}
