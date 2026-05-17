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
	let inputEl: HTMLInputElement;

	function handleFiles(files: FileList | null) {
		const next = files && files.length > 0 ? files[0] : null;
		onchange(next);
	}

	function formatSize(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
	}
</script>

<div
	class="dropzone"
	class:dragging
	class:filled={!!file}
	role="button"
	tabindex="0"
	aria-label={label}
	data-testid={testid}
	ondragover={(e) => {
		e.preventDefault();
		dragging = true;
	}}
	ondragleave={() => (dragging = false)}
	ondrop={(e) => {
		e.preventDefault();
		dragging = false;
		handleFiles(e.dataTransfer?.files ?? null);
	}}
	onclick={() => inputEl.click()}
	onkeydown={(e) => {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			inputEl.click();
		}
	}}
>
	<input
		bind:this={inputEl}
		type="file"
		{accept}
		class="sr-only"
		data-testid={testid ? `${testid}-input` : undefined}
		onchange={(e) => handleFiles((e.currentTarget as HTMLInputElement).files)}
	/>

	{#if file}
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
				class="btn ghost remove"
				onclick={(e) => {
					e.stopPropagation();
					onchange(null);
				}}
				aria-label={`Remove ${file.name}`}
			>
				Remove
			</button>
		</div>
	{:else}
		<div class="empty">
			<strong>{label}{required ? ' *' : ''}</strong>
			<span>Drop a file or click to browse</span>
			{#if hint}<span class="hint">{hint}</span>{/if}
		</div>
	{/if}
</div>

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
	.dropzone:focus-visible {
		border-color: var(--accent);
		background: color-mix(in srgb, var(--accent-soft) 50%, var(--surface));
	}
	.dropzone.dragging {
		border-color: var(--accent);
		background: var(--accent-soft);
		box-shadow: var(--shadow-md);
	}
	.dropzone.filled {
		border-style: solid;
		border-color: var(--border);
	}

	.empty {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		color: var(--text-muted);
	}
	.empty strong {
		color: var(--text);
	}
	.hint {
		font-size: 0.82rem;
		color: var(--text-subtle);
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
		font-size: 0.85rem;
		padding: 0.3rem 0.7rem;
	}
</style>
