<script lang="ts">
	import { downloadRunArchive } from '$lib/api';

	interface Props {
		runId: string;
	}

	let { runId }: Props = $props();

	let pending = $state(false);
	let error = $state<string | null>(null);

	// The archive is fetched (not linked) so the x-client-id header goes
	// with it, which means the save has to be driven from script: park the
	// blob on an object URL, click it, then release it. Skipping the revoke
	// leaks the whole zip for the life of the document.
	async function save() {
		pending = true;
		error = null;
		try {
			const blob = await downloadRunArchive(runId);
			const url = URL.createObjectURL(blob);
			try {
				const a = document.createElement('a');
				a.href = url;
				a.download = `run-${runId}.zip`;
				a.click();
			} finally {
				URL.revokeObjectURL(url);
			}
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			pending = false;
		}
	}
</script>

<button
	type="button"
	class="btn secondary"
	onclick={save}
	disabled={pending}
	data-testid="download-all"
>
	{pending ? 'Zipping…' : 'Download all (.zip)'}
</button>

{#if error}
	<p class="archive-error" role="alert" data-testid="download-all-error">
		Couldn’t build the archive: {error}
	</p>
{/if}

<style>
	/* Full-row so the message lands under the button rather than being
	   squeezed into the flex actions row beside it. */
	.archive-error {
		flex-basis: 100%;
		margin: var(--space-2) 0 0;
		color: var(--danger);
		font-size: 0.9rem;
	}
</style>
