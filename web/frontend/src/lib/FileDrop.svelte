<script lang="ts">
	interface Props {
		label: string;
		accept: string;
		file: File | null;
		required?: boolean;
		hint?: string;
		testid?: string;
		onchange: (file: File | null) => void;
	}

	let { label, accept, file, required = false, hint = '', testid, onchange }: Props = $props();

	let dragging = $state(false);
	let rejected = $state<string | null>(null);

	const inputId = $derived(`${testid ?? label.replace(/\s+/g, '-')}-input`);
	const hintId = $derived(`${inputId}-hint`);

	// The native `accept` only filters the browse dialog; drag-and-drop ignores
	// it. Validate the dropped extension so a wrong file can't slip through and
	// fail later as an opaque server error.
	function acceptsExtension(name: string): boolean {
		const exts = accept
			.split(',')
			.map((s) => s.trim().toLowerCase())
			.filter((s) => s.startsWith('.'));
		if (exts.length === 0) return true;
		const lower = name.toLowerCase();
		return exts.some((ext) => lower.endsWith(ext));
	}

	function handleFiles(files: FileList | null) {
		const next = files && files.length > 0 ? files[0] : null;
		if (next && !acceptsExtension(next.name)) {
			rejected = `${next.name} isn’t an accepted type (${accept}).`;
			return;
		}
		rejected = null;
		onchange(next);
	}

	function formatSize(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
	}

	// Drop handling shared by both states. svelte-ignore: the wrappers carry
	// drag handlers but are not click/keyboard targets — the <label>/<input>
	// and the Remove <button> provide the real, accessible interactions.
	function onDrop(e: DragEvent) {
		e.preventDefault();
		dragging = false;
		handleFiles(e.dataTransfer?.files ?? null);
	}
	function onDragOver(e: DragEvent) {
		e.preventDefault();
		dragging = true;
	}
</script>

{#if file}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="dropzone filled"
		data-testid={testid}
		ondragover={onDragOver}
		ondragleave={() => (dragging = false)}
		ondrop={onDrop}
	>
		<input
			id={inputId}
			type="file"
			{accept}
			class="sr-only"
			aria-required={required}
			data-testid={testid ? `${testid}-input` : undefined}
			onchange={(e) => handleFiles((e.currentTarget as HTMLInputElement).files)}
		/>
		<div class="file-meta">
			<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
				<path
					d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6"
					fill="none"
					stroke="currentColor"
					stroke-width="1.5"
					stroke-linejoin="round"
				/>
			</svg>
			<div>
				<div class="file-name">{file.name}</div>
				<div class="file-size">{formatSize(file.size)}</div>
			</div>
			<button
				type="button"
				class="btn ghost small remove"
				onclick={() => onchange(null)}
				aria-label={`Remove ${file.name}`}
			>
				Remove
			</button>
		</div>
	</div>
{:else}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<label
		class="dropzone"
		class:dragging
		data-testid={testid}
		ondragover={onDragOver}
		ondragleave={() => (dragging = false)}
		ondrop={onDrop}
	>
		<input
			id={inputId}
			type="file"
			{accept}
			class="sr-only"
			aria-required={required}
			aria-describedby={hint || rejected ? hintId : undefined}
			data-testid={testid ? `${testid}-input` : undefined}
			onchange={(e) => handleFiles((e.currentTarget as HTMLInputElement).files)}
		/>
		<span class="empty">
			<strong>{label}{required ? ' *' : ''}</strong>
			<span>Drop a file or click to browse</span>
			{#if rejected}
				<span class="hint reject" id={hintId} role="alert">{rejected}</span>
			{:else if hint}
				<span class="hint" id={hintId}>{hint}</span>
			{/if}
		</span>
	</label>
{/if}

<style>
	.dropzone {
		display: block;
		border: 1.5px dashed var(--border-strong);
		border-radius: var(--radius-md);
		padding: var(--space-4);
		background: var(--surface);
		cursor: pointer;
		transition:
			border-color 0.12s,
			background 0.12s,
			box-shadow 0.12s;
	}
	.dropzone:hover,
	.dropzone:focus-within {
		border-color: var(--accent);
		background: color-mix(in srgb, var(--accent-soft) 50%, var(--surface));
	}
	/* Route the focus ring to the visible dropzone (the real <input> is
	   visually hidden but keyboard-focusable). */
	.dropzone:focus-within {
		box-shadow: var(--focus-ring);
	}
	.dropzone.dragging {
		border-color: var(--accent);
		background: var(--accent-soft);
		box-shadow: var(--shadow-md);
	}
	.dropzone.filled {
		border-style: solid;
		border-color: var(--border);
		cursor: default;
	}

	.empty {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
		color: var(--text-muted);
	}
	.empty strong {
		color: var(--text);
	}
	.hint {
		font-size: 0.82rem;
		color: var(--text-subtle);
	}
	.hint.reject {
		color: var(--danger);
		font-weight: 500;
	}

	.file-meta {
		display: flex;
		align-items: center;
		gap: var(--space-3);
		color: var(--text);
	}
	.file-meta svg {
		color: var(--accent);
		flex: none;
	}
	.file-name {
		font-weight: 600;
	}
	.file-size {
		font-size: 0.82rem;
		color: var(--text-subtle);
	}
	.remove {
		margin-left: auto;
	}
</style>
