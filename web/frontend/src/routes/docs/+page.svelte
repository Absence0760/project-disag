<script lang="ts">
	// Static documentation page. No data fetching — this is a long-form,
	// visual explainer of what the toolkit does and how a run flows through
	// the system. Each section has an id so the on-page contents can deep-link.

	import { DOC_PAGES } from '$lib/docMeta';

	type TocItem = { id: string; label: string };

	const toc: TocItem[] = [
		{ id: 'big-picture', label: 'The big picture' },
		{ id: 'how-a-run-works', label: 'How a run works' },
		{ id: 'disaggregation', label: 'Disaggregation' },
		{ id: 'methods', label: 'Choosing a method' },
		{ id: 'exceedance', label: 'Exceedance curves' },
		{ id: 'file-formats', label: 'File formats' },
		{ id: 'deeper', label: 'Go deeper' }
	];

	// The six disag methods, paired with a one-line "reach for this when…".
	const methods: Array<{
		n: number;
		title: string;
		when: string;
		needs: string;
	}> = [
		{
			n: 0,
			title: 'One file',
			when: 'You have one clean daily gauge and are happy to drop any month with a gap.',
			needs: 'monthly + 1 daily'
		},
		{
			n: 1,
			title: 'Patch (calendar)',
			when: 'One gauge with occasional gaps — borrow the missing days from the same calendar month in a similar year.',
			needs: 'monthly + 1 daily'
		},
		{
			n: 2,
			title: 'Patch (file)',
			when: 'You have a second gauge to fall back on whenever the first one is blank.',
			needs: 'monthly + 2 daily'
		},
		{
			n: 3,
			title: 'Incremental',
			when: 'You want the runoff between two gauges (e.g. the catchment below a dam): shape = file 1 − file 2.',
			needs: 'monthly + 2 daily'
		},
		{
			n: 4,
			title: 'Even',
			when: 'No daily record exists anywhere — spread the month evenly across its days.',
			needs: 'monthly only'
		},
		{
			n: 5,
			title: 'Patch (exceedance)',
			when: 'Both gauges have holes — synthesise a donor month from another river at the same percentile rank.',
			needs: 'monthly + 1–2 daily'
		}
	];

	// Worked disaggregation numbers, reused by the bar chart and the table so
	// the visual and the figures can never drift apart.
	const dayShape = [
		{ d: 1, obs: 5.498 },
		{ d: 2, obs: 5.437 },
		{ d: 3, obs: 5.532 },
		{ d: 4, obs: 5.21 },
		{ d: 5, obs: 4.74 },
		{ d: 6, obs: 4.95 },
		{ d: 7, obs: 6.12 },
		{ d: 8, obs: 7.04 },
		{ d: 9, obs: 6.31 },
		{ d: 10, obs: 5.12 }
	];
	const obsSumFull = 141.86; // ΣQobs over all 30 days (from docs/problem.md)
	const genMonthly = 6.0; // Mm³ for June, from the worked example
	const MM3_PER_DAY_TO_CUMECS = 1e6 / 86400;
	const maxObs = Math.max(...dayShape.map((x) => x.obs));

	function scaled(obs: number): number {
		return genMonthly * (obs / obsSumFull) * MM3_PER_DAY_TO_CUMECS;
	}

	// Flow-duration curve geometry. Plot area is x:[60,520], y:[20,230],
	// flow axis 0–4 Mm³, exceedance axis 0–100%.
	const fdcPoints: Array<[number, number]> = [
		[100, 0.29],
		[97.14, 1.034],
		[75.71, 2.336],
		[50, 2.708],
		[24.29, 3.08],
		[8.57, 3.638],
		[4.29, 3.824]
	];
	const fdcX = (pct: number) => 60 + ((100 - pct) / 100) * 460;
	const fdcY = (flow: number) => 230 - (flow / 4) * 200;
	const fdcPolyline = fdcPoints.map(([p, f]) => `${fdcX(p)},${fdcY(f)}`).join(' ');
	const q50x = fdcX(50);
	const q50y = fdcY(2.708);
</script>

<svelte:head>
	<title>Docs · How Disag-MD works</title>
	<meta
		name="description"
		content="A visual, plain-language guide to the Disag-MD hydrology toolkit: disaggregation, exceedance curves, the six methods, and the file formats."
	/>
</svelte:head>

<header class="page-head">
	<span class="badge">Documentation</span>
	<h1>How Disag-MD works</h1>
	<p class="lede">
		A plain-language tour of the toolkit — what each tool does, the idea behind it, and how your
		files travel from the browser to the answer. Skim the diagrams; read the captions if a number
		surprises you.
	</p>
</header>

<nav class="toc" aria-label="On this page">
	{#each toc as item (item.id)}
		<a href={`#${item.id}`}>{item.label}</a>
	{/each}
</nav>

<!-- ───────────────────────── Big picture ───────────────────────── -->
<section id="big-picture" class="doc-section">
	<h2>The big picture</h2>
	<p>
		Hydrologists often have streamflow data at one time resolution but need it at another. This
		toolkit covers the two moves that come up again and again, plus a small format converter:
	</p>

	<div class="trio">
		<article class="card pillar">
			<div class="pillar-icon" aria-hidden="true">
				<svg viewBox="0 0 48 48">
					<rect x="6" y="10" width="9" height="28" rx="2" fill="var(--accent)" />
					<path
						d="M20 24h8M24 20l4 4-4 4"
						fill="none"
						stroke="var(--text-subtle)"
						stroke-width="2.4"
						stroke-linecap="round"
						stroke-linejoin="round"
					/>
					<path
						d="M33 14l1.6 4 4 1.6-4 1.6L33 25.2 31.4 21.2l-4-1.6 4-1.6zM39 26l1 2.5 2.5 1-2.5 1L39 33l-1-2.5-2.5-1 2.5-1z"
						fill="var(--accent)"
						opacity="0.55"
					/>
				</svg>
			</div>
			<h3>Disag</h3>
			<p class="pillar-tag">Monthly&nbsp;→&nbsp;daily</p>
			<p>
				Turn a coarse monthly volume record into a believable daily series by borrowing the
				day-to-day shape from a real gauge and rescaling it.
			</p>
		</article>

		<article class="card pillar">
			<div class="pillar-icon" aria-hidden="true">
				<svg viewBox="0 0 48 48">
					<path
						d="M6 12c8 0 6 26 14 26s10-22 18-22"
						fill="none"
						stroke="var(--accent)"
						stroke-width="2.6"
						stroke-linecap="round"
					/>
					<line x1="6" y1="40" x2="42" y2="40" stroke="var(--border-strong)" stroke-width="1.6" />
					<line x1="6" y1="40" x2="6" y2="8" stroke="var(--border-strong)" stroke-width="1.6" />
					<circle cx="24" cy="26" r="2.4" fill="var(--accent)" />
				</svg>
			</div>
			<h3>Exceed</h3>
			<p class="pillar-tag">Flow&nbsp;frequency</p>
			<p>
				Build a flow-duration curve: for what fraction of the time is the flow at or above a given
				level? One curve per month or season.
			</p>
		</article>

		<article class="card pillar">
			<div class="pillar-icon" aria-hidden="true">
				<svg viewBox="0 0 48 48">
					<rect
						x="8"
						y="9"
						width="14"
						height="18"
						rx="2"
						fill="none"
						stroke="var(--accent)"
						stroke-width="2.2"
					/>
					<rect x="26" y="21" width="14" height="18" rx="2" fill="var(--accent)" opacity="0.85" />
					<path
						d="M22 18h6M24 15l4 3-4 3"
						fill="none"
						stroke="var(--text-subtle)"
						stroke-width="2.2"
						stroke-linecap="round"
						stroke-linejoin="round"
					/>
				</svg>
			</div>
			<h3>Convert</h3>
			<p class="pillar-tag">Reformat</p>
			<p>
				Translate a monthly file from another modelling layout into the exact format Disag reads —
				no retyping, no silent parse errors.
			</p>
		</article>
	</div>
</section>

<!-- ───────────────────────── How a run works ───────────────────────── -->
<section id="how-a-run-works" class="doc-section">
	<h2>How a run works</h2>
	<p>
		Everything runs serverless. Your file never touches a long-lived server: the browser uploads it
		straight to storage with a one-time signed link, a function processes it, and you download the
		result through another signed link. Nothing is installed and nothing persists beyond the run.
	</p>

	<figure class="diagram">
		<svg viewBox="0 0 760 200" role="img" aria-labelledby="flow-title flow-desc">
			<title id="flow-title">Request flow</title>
			<desc id="flow-desc"
				>The browser uploads inputs to S3, asks the API to run the job, the Lambda reads the inputs,
				runs the Python tool, writes outputs back to S3, and the browser downloads them.</desc
			>

			<!-- nodes -->
			<g class="node">
				<rect x="16" y="74" width="118" height="52" rx="10" />
				<text x="75" y="96">Your browser</text>
				<text x="75" y="113" class="sub">uploads &amp; downloads</text>
			</g>
			<g class="node">
				<rect x="322" y="20" width="118" height="48" rx="10" />
				<text x="381" y="42">API + Lambda</text>
				<text x="381" y="58" class="sub">runs the Python</text>
			</g>
			<g class="node accent-node">
				<rect x="322" y="132" width="118" height="48" rx="10" />
				<text x="381" y="154">S3 storage</text>
				<text x="381" y="170" class="sub">inputs / outputs</text>
			</g>
			<g class="node">
				<rect x="626" y="74" width="118" height="52" rx="10" />
				<text x="685" y="96">disag / exceed</text>
				<text x="685" y="113" class="sub">stdlib Python</text>
			</g>

			<!-- edges -->
			<g class="edge">
				<path d="M134 104 C 210 104, 240 156, 320 156" marker-end="url(#arrow)" />
				<text x="205" y="146">1 · PUT file</text>
			</g>
			<g class="edge">
				<path d="M134 96 C 220 96, 250 44, 320 44" marker-end="url(#arrow)" />
				<text x="200" y="66">2 · run job</text>
			</g>
			<g class="edge">
				<path d="M381 68 L 381 130" marker-end="url(#arrow)" />
				<text x="430" y="104">3 · read inputs</text>
			</g>
			<g class="edge">
				<path d="M440 44 C 540 44, 560 100, 624 100" marker-end="url(#arrow)" />
				<text x="540" y="64">4 · compute</text>
			</g>
			<g class="edge">
				<path d="M624 104 C 545 116, 470 150, 442 156" marker-end="url(#arrow)" />
				<text x="540" y="150">5 · write output</text>
			</g>
			<g class="edge">
				<path d="M320 168 C 230 178, 170 150, 132 124" marker-end="url(#arrow)" />
				<text x="210" y="190">6 · GET result</text>
			</g>

			<defs>
				<marker
					id="arrow"
					viewBox="0 0 10 10"
					refX="8"
					refY="5"
					markerWidth="7"
					markerHeight="7"
					orient="auto-start-reverse"
				>
					<path d="M0 0 L10 5 L0 10 z" fill="var(--text-subtle)" />
				</marker>
			</defs>
		</svg>
		<figcaption>
			The signed upload/download links are short-lived (one hour by default). Each run gets its own
			id, and previous runs are listed on the <a href="/history">History</a> page.
		</figcaption>
	</figure>
</section>

<!-- ───────────────────────── Disaggregation ───────────────────────── -->
<section id="disaggregation" class="doc-section">
	<h2>Disaggregation: monthly volume, daily shape</h2>
	<p>
		You can't just split a month's volume evenly across its days — that erases the floods and dry
		spells that drive every engineering decision. Instead, Disag <strong>borrows the shape</strong>
		of a real observed day-by-day record and <strong>rescales it</strong> so the days still add up to
		your target monthly volume.
	</p>

	<div
		class="formula"
		role="img"
		aria-label="Generated daily flow equals generated monthly volume times observed daily over the sum of observed daily, times one million over eighty-six thousand four hundred."
	>
		<span class="f-out">Q<sub>day</sub></span>
		<span class="f-op">=</span>
		<span class="f-term f-vol">Q<sub>month</sub></span>
		<span class="f-op">×</span>
		<span class="f-frac">
			<span class="f-num">Q<sub>obs</sub>[day]</span>
			<span class="f-bar"></span>
			<span class="f-den">Σ Q<sub>obs</sub></span>
		</span>
		<span class="f-op">×</span>
		<span class="f-term f-unit">10⁶ ⁄ 86400</span>
	</div>
	<p class="formula-key">
		<span><span class="key-swatch vol"></span> the volume you want the month to total</span>
		<span><span class="key-swatch shape"></span> the day's share of the borrowed shape</span>
		<span><span class="key-swatch unit"></span> Mm³/day → m³/s unit conversion</span>
	</p>

	<p>
		Here's the first 10 days of the worked example from the docs: a generated <strong
			>June volume of {genMonthly.toFixed(1)} Mm³</strong
		>
		borrowing the shape of an observed June (whose 30 days sum to {obsSumFull} m³/s). The left bars are
		the borrowed shape; the right bars are the same pattern rescaled to hit the target volume.
	</p>

	<figure class="diagram">
		<div class="twin-charts">
			<div class="mini-chart">
				<span class="chart-title">Observed shape <small>(m³/s)</small></span>
				<div class="bars">
					{#each dayShape as row (row.d)}
						<div class="bar-col">
							<div
								class="bar obs"
								style={`height:${(row.obs / maxObs) * 100}%`}
								title={`Day ${row.d}: ${row.obs} m³/s observed`}
							></div>
							<span class="bar-label">{row.d}</span>
						</div>
					{/each}
				</div>
			</div>

			<div class="twin-arrow" aria-hidden="true">
				<svg viewBox="0 0 40 24"
					><path
						d="M2 12h32M28 6l8 6-8 6"
						fill="none"
						stroke="var(--accent)"
						stroke-width="2.4"
						stroke-linecap="round"
						stroke-linejoin="round"
					/></svg
				>
				<span>rescale</span>
			</div>

			<div class="mini-chart">
				<span class="chart-title">Disaggregated <small>(m³/s)</small></span>
				<div class="bars">
					{#each dayShape as row (row.d)}
						<div class="bar-col">
							<div
								class="bar gen"
								style={`height:${(row.obs / maxObs) * 100}%`}
								title={`Day ${row.d}: ${scaled(row.obs).toFixed(3)} m³/s generated`}
							></div>
							<span class="bar-label">{row.d}</span>
						</div>
					{/each}
				</div>
			</div>
		</div>
		<figcaption>
			Same silhouette, different vertical scale — the relative day-to-day variation is preserved
			while the absolute level is pinned to your monthly volume. Day 1 works out to
			<code
				>{genMonthly} × ({dayShape[0].obs} / {obsSumFull}) × 11.574 ≈ {scaled(
					dayShape[0].obs
				).toFixed(3)} m³/s</code
			>.
		</figcaption>
	</figure>

	<details class="worked">
		<summary>See the first 10 days as numbers</summary>
		<table class="data-table">
			<thead>
				<tr><th>Day</th><th>Observed (m³/s)</th><th>Share of Σ</th><th>Disaggregated (m³/s)</th></tr
				>
			</thead>
			<tbody>
				{#each dayShape as row (row.d)}
					<tr>
						<td>{row.d}</td>
						<td>{row.obs.toFixed(3)}</td>
						<td>{((row.obs / obsSumFull) * 100).toFixed(2)}%</td>
						<td>{scaled(row.obs).toFixed(3)}</td>
					</tr>
				{/each}
			</tbody>
		</table>
		<p class="muted small">
			Shares are of the full 30-day sum ({obsSumFull}), so these ten rows don't total 100%.
		</p>
	</details>
</section>

<!-- ───────────────────────── Methods ───────────────────────── -->
<section id="methods" class="doc-section">
	<h2>Choosing a method</h2>
	<p>
		The honest part of disaggregation is what to do when the observed record has gaps — real gauges
		fail, get vandalised, or were installed late. Disag gives you six strategies. Pick the cheapest
		one that still gives you a usable signal; the report logs every patch so you can see where the
		output is real versus synthetic.
	</p>

	<figure class="diagram decision">
		<svg viewBox="0 0 720 250" role="img" aria-labelledby="dec-title">
			<title id="dec-title">A decision guide for picking a disaggregation method</title>
			<defs>
				<marker
					id="arrow2"
					viewBox="0 0 10 10"
					refX="8"
					refY="5"
					markerWidth="7"
					markerHeight="7"
					orient="auto-start-reverse"
				>
					<path d="M0 0 L10 5 L0 10 z" fill="var(--text-subtle)" />
				</marker>
			</defs>

			<!-- Q1 -->
			<g class="q">
				<rect x="10" y="100" width="150" height="50" rx="8" />
				<text x="85" y="121">Any daily</text>
				<text x="85" y="138">gauge at all?</text>
			</g>
			<g class="edge2">
				<path d="M85 100 V60 H190" marker-end="url(#arrow2)" />
				<text x="120" y="52" class="lbl no">no</text>
			</g>
			<g class="leaf m4">
				<rect x="190" y="38" width="120" height="44" rx="8" />
				<text x="250" y="56">Method 4</text>
				<text x="250" y="72" class="sub">Even</text>
			</g>

			<g class="edge2">
				<path d="M160 125 H210" marker-end="url(#arrow2)" />
				<text x="185" y="117" class="lbl yes">yes</text>
			</g>

			<!-- Q2 -->
			<g class="q">
				<rect x="210" y="100" width="150" height="50" rx="8" />
				<text x="285" y="121">Two gauges,</text>
				<text x="285" y="138">want the gap?</text>
			</g>
			<g class="edge2">
				<path d="M340 100 V60 H400" marker-end="url(#arrow2)" />
				<text x="370" y="52" class="lbl">below a dam</text>
			</g>
			<g class="leaf m3">
				<rect x="400" y="38" width="120" height="44" rx="8" />
				<text x="460" y="56">Method 3</text>
				<text x="460" y="72" class="sub">Incremental</text>
			</g>

			<g class="edge2">
				<path d="M360 125 H410" marker-end="url(#arrow2)" />
			</g>

			<!-- Q3 -->
			<g class="q">
				<rect x="410" y="100" width="150" height="50" rx="8" />
				<text x="485" y="121">How bad are</text>
				<text x="485" y="138">the gaps?</text>
			</g>

			<g class="edge2">
				<path d="M485 150 V196 H120 V150" marker-end="url(#arrow2)" />
				<text x="300" y="212" class="lbl">none → Method 0 (One file)</text>
			</g>

			<g class="leaf-stack">
				<g class="leaf m1">
					<rect x="600" y="92" width="112" height="30" rx="7" />
					<text x="656" y="111">1 · calendar</text>
				</g>
				<g class="leaf m2">
					<rect x="600" y="128" width="112" height="30" rx="7" />
					<text x="656" y="147">2 · second file</text>
				</g>
				<g class="leaf m5">
					<rect x="600" y="164" width="112" height="30" rx="7" />
					<text x="656" y="183">5 · exceedance</text>
				</g>
			</g>
			<g class="edge2">
				<path d="M560 132 C 582 143, 586 143, 596 143" marker-end="url(#arrow2)" />
				<text x="578" y="120" class="lbl">some</text>
			</g>
		</svg>
		<figcaption>
			A rough guide, not a rule. Method 1 patches from a similar year, method 2 from a second gauge,
			and method 5 synthesises a donor month from another river when both gauges run dry.
		</figcaption>
	</figure>

	<div class="method-cards">
		{#each methods as m (m.n)}
			<article class="card method">
				<div class="method-top">
					<span class="method-n">{m.n}</span>
					<h3>{m.title}</h3>
				</div>
				<p>{m.when}</p>
				<span class="badge">{m.needs}</span>
			</article>
		{/each}
	</div>
</section>

<!-- ───────────────────────── Exceedance ───────────────────────── -->
<section id="exceedance" class="doc-section">
	<h2>Exceedance curves: how often is flow ≥ X?</h2>
	<p>
		The flow-duration curve is the workhorse plot of practical hydrology. Sort the values, count how
		many sit at or above each level, divide by the total, and you have an exceedance percentage.
		<strong>Q95</strong> (the flow beaten 95% of the time) is the standard low-flow index;
		<strong>Q50</strong> is the median. Exceed computes one curve per calendar month — so January isn't
		averaged together with July.
	</p>

	<figure class="diagram">
		<svg viewBox="0 0 560 280" class="fdc" role="img" aria-labelledby="fdc-title fdc-desc">
			<title id="fdc-title">A flow-duration curve for January</title>
			<desc id="fdc-desc"
				>Flow falls steeply as exceedance percentage rises: every January exceeds 0.29 Mm³, the
				median is about 2.7, and only a few percent of years exceed 3.8.</desc
			>
			<!-- axes -->
			<line x1="60" y1="20" x2="60" y2="230" class="axis" />
			<line x1="60" y1="230" x2="520" y2="230" class="axis" />

			<!-- y gridlines + labels (flow Mm³) -->
			{#each [0, 1, 2, 3, 4] as v (v)}
				<g>
					<line x1="56" y1={230 - (v / 4) * 200} x2="520" y2={230 - (v / 4) * 200} class="grid" />
					<text x="50" y={234 - (v / 4) * 200} class="tick y">{v}</text>
				</g>
			{/each}

			<!-- x labels (exceedance %) -->
			{#each [0, 25, 50, 75, 100] as p (p)}
				<text x={60 + (p / 100) * 460} y="248" class="tick x">{p}%</text>
			{/each}

			<!-- the curve: (exceedance%, flow) points from docs/problem.md SINDILA Jan -->
			<polyline class="curve-line" points={fdcPolyline} />

			<!-- Q50 marker -->
			<line x1={q50x} y1={q50y} x2={q50x} y2="230" class="marker" />
			<circle cx={q50x} cy={q50y} r="4" class="marker-dot" />
			<text x={q50x + 8} y={q50y - 6} class="callout">Q50 ≈ 2.7 Mm³</text>

			<!-- axis titles -->
			<text x="290" y="270" class="axis-title">Exceedance % (fraction of years ≥ flow)</text>
			<text x="18" y="125" class="axis-title" transform="rotate(-90 18 125)">Flow (Mm³)</text>
		</svg>
		<figcaption>
			Reading it: in half of all years January's volume was at least ~2.7 Mm³; in only ~4% of years
			did it top 3.8. That's exactly the kind of statement a yield study or environmental-flow
			licence is built on. <strong>Seasonal</strong> mode pools months for a bigger sample;
			<strong>Matching</strong> mode lines a daily curve up against its monthly source to check a disaggregation
			didn't distort the distribution.
		</figcaption>
	</figure>
</section>

<!-- ───────────────────────── File formats ───────────────────────── -->
<section id="file-formats" class="doc-section">
	<h2>File formats (and their traps)</h2>
	<p>
		The inputs are domain-specific fixed-layout text files — not CSV. The reader handles the quirks
		for you, but it helps to know what they are, because getting them wrong is silent.
	</p>

	<div class="format-grid">
		<article class="card fmt">
			<h3><code>.mon</code> — monthly volumes</h3>
			<p>
				Rows are keyed by <strong>hydro year</strong> (October → September), not calendar year. So
				October of year <em>N</em> and the following January both live on the row labelled
				<em>N</em>. Mind the off-by-one when you map back to calendar months.
			</p>
			<div class="hydro" aria-hidden="true">
				<span class="hy-label">hydro-year row 1965 →</span>
				<div class="hy-months">
					{#each ['O', 'N', 'D', 'J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S'] as mo, i (i)}
						<span class="hy-mo" class:nextyear={i >= 3}>{mo}</span>
					{/each}
				</div>
				<span class="hy-key">
					<span class="hy-swatch this"></span> calendar 1965
					<span class="hy-swatch next"></span> calendar 1966
				</span>
			</div>
		</article>

		<article class="card fmt">
			<h3><code>.day</code> — daily flows</h3>
			<p>
				Fixed-width: each daily value is a <strong>7-character</strong> right-justified column.
				Don't split on whitespace — negative sentinels run together with no separator, so
				<code>.split()</code> produces unparsable tokens.
			</p>
			<div class="fixed-demo" aria-hidden="true">
				<div class="fw-row good">
					<span class="cell"> 5.498</span><span class="cell"> 5.437</span><span class="cell"
						>-99.990</span
					><span class="cell">-99.990</span>
				</div>
				<span class="fw-note good-note"
					>✓ read as four 7-char columns →
					<code>5.498, 5.437, −99.99, −99.99</code></span
				>
				<div class="fw-row bad"><span class="cell-bad">-99.990-99.990</span></div>
				<span class="fw-note bad-note">✗ <code>.split()</code> sees one token and chokes</span>
			</div>
			<p class="muted small">
				Two more gotchas the reader absorbs: years are sometimes 2-digit (<code>51</code>) and
				sometimes 4-digit (<code>2019</code>); and the first number on each record is a monthly
				total, not a daily value.
			</p>
		</article>
	</div>
</section>

<!-- ───────────────────────── Go deeper ───────────────────────── -->
<section id="deeper" class="doc-section deeper">
	<h2>Go deeper</h2>
	<p>
		This page is the friendly version. The full technical write-ups — exact formulae, per-method
		edge cases, and the on-disk byte layout — are published here as their own pages:
	</p>
	<div class="ref-grid">
		{#each DOC_PAGES as doc (doc.slug)}
			<a class="card ref" href={`/docs/${doc.slug}`}>
				<h3>{doc.label}</h3>
				<p>{doc.blurb}</p>
			</a>
		{/each}
	</div>
	<div class="actions">
		<a class="btn" href="/run">Try a run →</a>
		<a class="btn ghost" href="/">Back to overview</a>
	</div>
</section>

<style>
	.page-head {
		max-width: 720px;
		margin-bottom: var(--space-5);
	}
	.page-head .badge {
		margin-bottom: var(--space-3);
	}
	.lede {
		font-size: 1.08rem;
		color: var(--text-muted);
	}

	/* Sticky on-page contents */
	.toc {
		position: sticky;
		top: calc(var(--header-h) + var(--space-2));
		z-index: 5;
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1);
		padding: var(--space-2);
		margin-bottom: var(--space-6);
		background: color-mix(in srgb, var(--surface) 88%, transparent);
		backdrop-filter: saturate(140%) blur(8px);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
	}
	.toc a {
		padding: 0.3rem 0.7rem;
		border-radius: var(--radius-sm);
		font-size: 0.88rem;
		font-weight: 500;
		color: var(--text-muted);
	}
	.toc a:hover {
		background: var(--surface-2);
		color: var(--text);
		text-decoration: none;
	}

	.doc-section {
		margin: var(--space-8) 0;
		/* Clear the sticky header plus the sticky on-page TOC below it. */
		scroll-margin-top: calc(var(--header-h) + var(--space-8) * 1.5);
	}
	.doc-section > p {
		max-width: 680px;
	}

	/* Three pillars */
	.trio {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: var(--space-4);
		margin-top: var(--space-4);
	}
	.pillar {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}
	.pillar h3 {
		margin: 0;
	}
	.pillar-tag {
		margin: 0;
		font-size: 0.78rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--text-subtle);
	}
	.pillar p:last-child {
		margin: 0;
		font-size: 0.92rem;
	}
	.pillar-icon svg {
		width: 44px;
		height: 44px;
	}

	/* Diagrams */
	.diagram {
		margin: var(--space-5) 0;
	}
	.diagram svg {
		width: 100%;
		height: auto;
		display: block;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius-lg);
		padding: var(--space-3);
	}
	figcaption {
		margin-top: var(--space-3);
		font-size: 0.9rem;
		color: var(--text-muted);
		max-width: 680px;
	}

	/* Flow diagram nodes/edges */
	.node rect {
		fill: var(--surface-2);
		stroke: var(--border-strong);
		stroke-width: 1.2;
	}
	.node.accent-node rect {
		fill: var(--accent-soft);
		stroke: var(--accent);
	}
	.node text {
		text-anchor: middle;
		fill: var(--text);
		font-size: 13px;
		font-weight: 600;
	}
	.node text.sub {
		fill: var(--text-subtle);
		font-size: 10.5px;
		font-weight: 500;
	}
	.edge path {
		fill: none;
		stroke: var(--text-subtle);
		stroke-width: 1.6;
	}
	.edge text {
		text-anchor: middle;
		fill: var(--text-muted);
		font-size: 11px;
		font-weight: 600;
	}

	/* Formula */
	.formula {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: var(--space-2);
		padding: var(--space-4) var(--space-5);
		margin: var(--space-4) 0 var(--space-3);
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius-lg);
		font-family: var(--font-mono);
		font-size: 1.05rem;
	}
	.f-op {
		color: var(--text-subtle);
	}
	.f-out {
		font-weight: 700;
		color: var(--text);
	}
	.f-vol {
		color: var(--accent);
		font-weight: 600;
	}
	.f-unit {
		color: var(--text-muted);
		font-size: 0.92rem;
	}
	.f-frac {
		display: inline-flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
	}
	.f-num,
	.f-den {
		padding: 0 0.3rem;
		font-size: 0.95rem;
	}
	.f-bar {
		width: 100%;
		height: 1.5px;
		background: var(--text-subtle);
		margin: 2px 0;
	}
	.formula-key {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-4);
		font-size: 0.85rem;
		color: var(--text-muted);
		max-width: none;
	}
	.formula-key span {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
	}
	.key-swatch {
		width: 11px;
		height: 11px;
		border-radius: 3px;
		display: inline-block;
	}
	.key-swatch.vol {
		background: var(--accent);
	}
	.key-swatch.shape {
		background: var(--text-subtle);
	}
	.key-swatch.unit {
		background: var(--border-strong);
	}

	/* Twin bar charts */
	.twin-charts {
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		align-items: end;
		gap: var(--space-3);
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius-lg);
		padding: var(--space-4);
	}
	.mini-chart {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}
	.chart-title {
		font-size: 0.82rem;
		font-weight: 600;
		color: var(--text-muted);
		text-align: center;
	}
	.chart-title small {
		color: var(--text-subtle);
		font-weight: 400;
	}
	.bars {
		display: flex;
		align-items: flex-end;
		gap: 4px;
		height: 130px;
	}
	.bar-col {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 4px;
		height: 100%;
		justify-content: flex-end;
	}
	.bar {
		width: 100%;
		border-radius: 3px 3px 0 0;
		min-height: 3px;
	}
	.bar.obs {
		background: var(--text-subtle);
	}
	.bar.gen {
		background: var(--accent);
	}
	.bar-label {
		font-size: 0.66rem;
		color: var(--text-subtle);
	}
	.twin-arrow {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 4px;
		padding-bottom: 28px;
	}
	.twin-arrow svg {
		width: 38px;
		height: 22px;
	}
	.twin-arrow span {
		font-size: 0.72rem;
		color: var(--accent);
		font-weight: 600;
	}

	/* Worked table */
	.worked {
		margin-top: var(--space-3);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		padding: var(--space-2) var(--space-4);
		background: var(--surface);
	}
	.worked summary {
		cursor: pointer;
		font-weight: 600;
		color: var(--text);
		padding: var(--space-2) 0;
	}
	.data-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.9rem;
		margin: var(--space-2) 0;
	}
	.data-table th,
	.data-table td {
		text-align: right;
		padding: 0.35rem 0.6rem;
		border-bottom: 1px solid var(--border);
		font-variant-numeric: tabular-nums;
	}
	.data-table th {
		color: var(--text-subtle);
		font-weight: 600;
		font-size: 0.8rem;
	}
	.data-table td:first-child,
	.data-table th:first-child {
		text-align: left;
	}

	/* Decision diagram */
	.decision .q rect {
		fill: var(--surface-2);
		stroke: var(--border-strong);
		stroke-width: 1.2;
	}
	.decision .q text {
		text-anchor: middle;
		fill: var(--text);
		font-size: 12px;
		font-weight: 600;
	}
	.decision .leaf rect,
	.decision .leaf-stack rect {
		fill: var(--accent-soft);
		stroke: var(--accent);
		stroke-width: 1.2;
	}
	.decision .leaf text {
		text-anchor: middle;
		fill: var(--text);
		font-size: 12px;
		font-weight: 600;
	}
	.decision .leaf text.sub {
		fill: var(--text-muted);
		font-size: 10px;
		font-weight: 500;
	}
	.decision .leaf-stack text {
		text-anchor: middle;
		fill: var(--text);
		font-size: 11px;
		font-weight: 600;
	}
	.decision .edge2 path {
		fill: none;
		stroke: var(--text-subtle);
		stroke-width: 1.5;
	}
	.decision .edge2 text,
	.decision .lbl {
		text-anchor: middle;
		fill: var(--text-muted);
		font-size: 10.5px;
		font-weight: 600;
	}
	.decision .lbl.yes {
		fill: var(--success);
	}
	.decision .lbl.no {
		fill: var(--danger);
	}

	/* Method cards */
	.method-cards {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
		gap: var(--space-3);
		margin-top: var(--space-4);
	}
	.method {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
		padding: var(--space-4);
	}
	.method-top {
		display: flex;
		align-items: center;
		gap: var(--space-2);
	}
	.method-top h3 {
		margin: 0;
		font-size: 1rem;
	}
	.method-n {
		font-family: var(--font-mono);
		font-size: 0.85rem;
		font-weight: 700;
		color: #fff;
		background: var(--accent);
		width: 1.7rem;
		height: 1.7rem;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--radius-sm);
		flex: 0 0 auto;
	}
	.method p {
		margin: 0;
		font-size: 0.9rem;
		flex: 1;
	}
	.method .badge {
		align-self: flex-start;
	}

	/* FDC curve */
	.fdc .axis {
		stroke: var(--border-strong);
		stroke-width: 1.4;
	}
	.fdc .grid {
		stroke: var(--border);
		stroke-width: 1;
		stroke-dasharray: 3 4;
	}
	.fdc .tick {
		fill: var(--text-subtle);
		font-size: 11px;
	}
	.fdc .tick.y {
		text-anchor: end;
	}
	.fdc .tick.x {
		text-anchor: middle;
	}
	.fdc .curve-line {
		fill: none;
		stroke: var(--accent);
		stroke-width: 2.6;
		stroke-linejoin: round;
		stroke-linecap: round;
	}
	.fdc .marker {
		stroke: var(--text-subtle);
		stroke-width: 1.2;
		stroke-dasharray: 3 3;
	}
	.fdc .marker-dot {
		fill: var(--accent);
	}
	.fdc .callout {
		fill: var(--text);
		font-size: 11px;
		font-weight: 600;
	}
	.fdc .axis-title {
		fill: var(--text-muted);
		font-size: 11px;
		text-anchor: middle;
	}

	/* File formats */
	.format-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
		gap: var(--space-4);
		margin-top: var(--space-4);
	}
	.fmt h3 {
		font-size: 1rem;
	}
	.fmt p {
		font-size: 0.92rem;
	}

	.hydro {
		margin-top: var(--space-2);
	}
	.hy-label {
		font-size: 0.78rem;
		color: var(--text-subtle);
		font-family: var(--font-mono);
	}
	.hy-months {
		display: flex;
		gap: 3px;
		margin: 0.4rem 0;
	}
	.hy-mo {
		flex: 1;
		text-align: center;
		padding: 0.35rem 0;
		font-size: 0.78rem;
		font-weight: 600;
		font-family: var(--font-mono);
		border-radius: var(--radius-sm);
		background: var(--accent-soft);
		color: var(--accent);
	}
	.hy-mo.nextyear {
		background: var(--surface-2);
		color: var(--text-muted);
	}
	.hy-key {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.76rem;
		color: var(--text-subtle);
		flex-wrap: wrap;
	}
	.hy-swatch {
		width: 10px;
		height: 10px;
		border-radius: 2px;
		display: inline-block;
	}
	.hy-swatch.this {
		background: var(--accent-soft);
		border: 1px solid var(--accent);
	}
	.hy-swatch.next {
		background: var(--surface-2);
		border: 1px solid var(--border-strong);
		margin-left: 0.6rem;
	}

	.fixed-demo {
		margin: var(--space-2) 0;
		font-family: var(--font-mono);
	}
	.fw-row {
		display: flex;
		font-size: 0.82rem;
		margin-top: 0.4rem;
	}
	.cell {
		border: 1px solid var(--border);
		border-right-width: 0;
		padding: 0.3rem 0.4rem;
		white-space: pre;
		background: var(--surface-2);
		color: var(--text);
	}
	.cell:last-child {
		border-right-width: 1px;
	}
	.cell-bad {
		border: 1px solid var(--danger);
		padding: 0.3rem 0.4rem;
		white-space: pre;
		background: var(--danger-soft);
		color: var(--danger);
	}
	.fw-note {
		display: block;
		font-size: 0.76rem;
		margin-top: 0.25rem;
		font-family: var(--font-sans);
	}
	.good-note {
		color: var(--success);
	}
	.bad-note {
		color: var(--danger);
	}

	.small {
		font-size: 0.82rem;
	}
	.muted {
		color: var(--text-subtle);
	}

	/* Go deeper */
	.ref-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
		gap: var(--space-3);
		margin-top: var(--space-4);
	}
	.ref {
		display: block;
		color: inherit;
		transition:
			border-color 0.12s,
			box-shadow 0.12s,
			transform 0.04s;
	}
	.ref:hover {
		border-color: var(--accent);
		box-shadow: var(--shadow-md);
		text-decoration: none;
		transform: translateY(-1px);
	}
	.ref h3 {
		margin: 0 0 var(--space-1);
		font-size: 1rem;
		color: var(--accent);
	}
	.ref p {
		margin: 0;
		font-size: 0.88rem;
		color: var(--text-muted);
	}
	.deeper .actions {
		display: flex;
		gap: var(--space-3);
		flex-wrap: wrap;
		margin-top: var(--space-5);
	}

	@media (max-width: 560px) {
		.twin-charts {
			grid-template-columns: 1fr;
		}
		.twin-arrow {
			transform: rotate(90deg);
			padding: 0;
		}
	}
</style>
