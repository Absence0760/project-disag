<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { getRun } from '$lib/api';
	import type { RunResult } from '$lib/types';

	let result = $state<RunResult | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);

	const runId = $page.params.run_id as string;

	onMount(async () => {
		try {
			result = await getRun(runId);
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			loading = false;
		}
	});

	function outputLabel(key: string | undefined): string {
		if (!key) return 'output';
		const m = key.match(/\.([a-z0-9]+)$/i);
		return m ? `.${m[1].toLowerCase()} output` : 'output';
	}

	function fmtDate(iso: string): string {
		return new Date(iso).toLocaleString(undefined, {
			year: 'numeric',
			month: 'short',
			day: '2-digit',
			hour: '2-digit',
			minute: '2-digit'
		});
	}
</script>

<svelte:head>
	<title>Run {runId} · Disag-MD</title>
</svelte:head>

<header class="page-head">
	<h1>Run <code>{runId}</code></h1>
	<p class="muted"><a href="/history">← Back to history</a></p>
</header>

{#if loading}
	<div class="card skeleton" data-testid="run-loading" aria-busy="true">
		<div class="skel skel-badge"></div>
		<div class="skel skel-title"></div>
		<div class="skel skel-line"></div>
		<div class="skel-actions">
			<div class="skel skel-btn"></div>
			<div class="skel skel-btn"></div>
		</div>
		<span class="sr-only">Loading run…</span>
	</div>
{:else if error}
	<div class="alert error card" role="alert" data-testid="run-error">
		<strong>Couldn’t load this run.</strong>
		<p>{error}</p>
		<p class="muted">
			Download links expire 1 hour after they’re issued; opening the run page re-issues fresh links,
			so a transient error here usually clears with a refresh.
		</p>
		<div class="actions">
			<a class="btn ghost" href="/history">Back to history</a>
		</div>
	</div>
{:else if result}
	<div class="alert success card success-card" data-testid="run-detail">
		<span class="badge success">{result.tool}</span>
		<h3>Created {fmtDate(result.created_at)}</h3>
		<p>Download links below are short-lived (1 hour by default).</p>
		<div class="actions">
			{#if result.output_url}
				<a class="btn" href={result.output_url} data-testid="download-output">
					Download {outputLabel(result.output_key)}
				</a>
			{/if}
			<a class="btn secondary" href={result.report_url} data-testid="download-report">
				Download .rep report
			</a>
			<a class="btn ghost" href="/history">View all runs →</a>
		</div>
	</div>
{/if}

<style>
	.page-head {
		margin-bottom: var(--space-5);
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-3);
		margin-top: var(--space-3);
	}
	.muted {
		color: var(--text-muted);
	}

	.skeleton {
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
	}
	.skel {
		border-radius: var(--radius-sm);
		background: linear-gradient(
			90deg,
			var(--surface-2) 0%,
			color-mix(in srgb, var(--surface-2) 70%, var(--border-strong)) 50%,
			var(--surface-2) 100%
		);
		background-size: 200% 100%;
		animation: shimmer 1.4s infinite;
	}
	.skel-badge {
		width: 4rem;
		height: 1.1rem;
		border-radius: 999px;
	}
	.skel-title {
		width: 60%;
		height: 1.3rem;
	}
	.skel-line {
		width: 80%;
		height: 0.9rem;
	}
	.skel-actions {
		display: flex;
		gap: var(--space-3);
		margin-top: var(--space-2);
	}
	.skel-btn {
		width: 9rem;
		height: 2.4rem;
		border-radius: var(--radius-md);
	}

	@keyframes shimmer {
		0% {
			background-position: 200% 0;
		}
		100% {
			background-position: -200% 0;
		}
	}
</style>
