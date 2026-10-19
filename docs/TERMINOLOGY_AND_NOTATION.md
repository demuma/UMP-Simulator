# Terminology, notation and mathematical contract

Version 1.3 — 2026-10-19. This is the project's canonical terminology for the presentation,
paper, dissertation and new documentation. It describes the implemented baseline and marks
future extensions explicitly. Earlier reviews retain historical/local notation; use this
reference when translating them into publication text. Code identifiers are mapped below;
this document does not rename APIs or implement new behavior.

## 1. Central distinction

**Aggregation is cell-bound and interval-bound. Functional regions determine constraints;
they do not become aggregation cells, buckets or independent clocks.**

A candidate refers to a quadtree cell C and a half-open time interval I. The constraints
for that candidate follow from the application's policy and every selected functional region
intersected by C. A region can contain many cells; one cell can intersect several regions.
Cells in the same region can have different observation histories and, in the opt-in local
controller, different aggregation intervals.

Use **cell-local temporal adaptation with coordinated merge groups** for the implemented
opt-in local mode. The earlier phrase **independent regional aggregation windows** is deprecated:
it incorrectly suggests that a semantic region owns one bucket/window or that region and
quadtree boundaries must coincide.

The current history API can reconstruct different intervals for different cells. The
default adaptive controller and publication coordinator use one common interval over
the entire sensor grid. The opt-in `cell_local` mode has independent spatial owner intervals
and coordinated parent handoffs; see [CELL_LOCAL_COORDINATION.md](CELL_LOCAL_COORDINATION.md).

## 2. Canonical terms

| Term | Meaning and usage |
|---|---|
| Road user | One simulated entity with an internal identity. A vehicle agent is one entity, not a count of its occupants. Use “agent” for the simulation implementation. |
| Ground truth (GT) | Private reference state, including actual simulated identity and position. It is distinct from the sensor's observation and the recipient release. |
| Realized trajectory | The time-indexed actual motion of a road user, denoted phi_u(t). |
| Planned path / waypoints | Intended route geometry. `Agent::trajectory` currently stores planned waypoints; it is not the recorded realized trajectory. |
| Observation | One road-user contribution in a measured sensor batch, with the information that sensor/adapter supplies. |
| Observation batch | One sensor's timestamped measurement result and status. A measured-empty batch is a valid observation opportunity. |
| Quadtree snapshot | Immutable spatial state/geometry for a frame; it is not a Policy Tree or an approved release. |
| Sensor frame | Renderer transport envelope that can combine multiple sensor IDs at one timestamp. It is not an aggregation window or a published aggregate. |
| Data cell | A spatial footprint represented by a data-quadtree node. Leaves are the finest available observation support; ancestors are candidate coarser support. |
| Functional region | Semantic geometry, such as carriageway, cycleway, footway or entrance, used to select policy requirements and possibly motion rules. |
| Movement corridor | Allowed traversable geometry/connectivity for motion. It may share geometry with a functional region but has a different role. |
| Metric | A defined measured quantity with inputs, units and unavailable cases. |
| Threshold / bound | A numeric minimum or maximum for a metric. |
| Constraint | A requirement that must hold. A numeric bound is one supported kind; new geometric rules require explicit implementation. |
| Application policy | The application's requirements plus supported execution choices. It is not itself the measured metric value. |
| Policy Tree | Immutable spatial lookup of effective requirements. It does not store road users or compute metric values. |
| Adaptation strategy | The deterministic order of permitted spatial and temporal actions. Current strategies are not learned RL policies or utility optimizers. |
| Candidate | A private aggregate considered for a cell/interval, with statistics and assessment. Passing a check is not the same lifecycle event as publication. |
| Bucket | A private logical cell/interval record over retained history, with identity/generation, role and lifecycle. It need not own copied raw data or be attached only to a leaf. |
| Coordination group | Cells whose pending decisions/publication must be reconciled, particularly for a parent merge. It is not defined by a region ID. |
| Spatial cut | Nonoverlapping selected quadtree nodes. A sparse/partial publication cut need not cover the whole sensor square. |
| Release | An immutable recipient-visible result after publication coordination. Private candidates, progress overlays and suppression diagnostics are not releases. |
| Suppression | Withholding candidate support. It does not mean the physical occupancy was zero. |
| Utility | Usefulness for a fixed declared application query. Use this term rather than “usability” in new scientific text. |
| Policy compliance | Satisfaction of the declared requirements. It is distinct from output availability, search completeness, optimality and empirical privacy. |

## 3. Symbols and indices

These are project conventions, not a claim that one universal notation exists across control
and reinforcement-learning literature. Typography/subscripts distinguish related quantities.
Local dummy indices must be declared where introduced.

| Symbol | Meaning | Unit / domain |
|---|---|---|
| $\Omega$ | Sensor coverage / spatial domain | subset of R^2, coordinates in m |
| $L$ | Side length of the current square coverage | m |
| $u,\mathcal U_{\mathrm{all}}$ | Road-user identity; set of road-user identities | internal identifiers |
| $\phi_u(t)$ | Realized position trajectory of u | R^2, m |
| $\mathcal U_{\mathrm{GT}}(t)$ | Road users present in the GT state at time t | IDs with a defined position at t |
| $P_u$ | Planned waypoint sequence | sequence of positions in m |
| $\sigma$ | Sensor identifier | one observation source |
| $a$ | Application identifier | one release/policy context |
| $\zeta$ | Stream context (run ID, sigma, a) | all following statistics are scoped to it |
| $\delta_\sigma$ | Sensor sampling period | ms in the implementation |
| $t_j$ | Scheduled sensor sample time | j delta_sigma, j >= 1 |
| $\Delta t_{\mathrm{sim}}$ | Simulation integration step | ms; separate from delta_sigma |
| $C$ | Data-quadtree cell and its spatial footprint | square subset of Omega |
| $\nu(C)$ | Encoded cell ID | integer, stream geometry required for physical location |
| $d(C),D$ | Cell depth; maximum observation depth | integer; larger depth means finer cells |
| $h(C),A(C)$ | Cell side length; cell area | m; m^2 |
| $R_r$ | Functional region with stable ID r | subset of Omega |
| $I_b=[t_b^-,t_b^+)$ | Candidate/bucket aggregation interval | half-open interval in simulation ms |
| $\Delta_b$ | Aggregation duration | t_b^+ - t_b^-, ms |
| $b=(C_b,I_b)$ | Geometric/temporal support of a candidate | implicit stream context zeta |
| $B_\beta$ | Private logical bucket identified by beta | metadata over retained history |
| $\mathcal O_{\sigma,j}$ | Timestamped sensor observation batch | measured or unavailable status |
| $\mathcal O(C,I)$ | Multiset of received road-user observations in C and I | observations, not distinct entities |
| $\mathcal U(C,I)$ | Union of observed road-user identities in C and I | set of internal IDs |
| $n(C,I)$ | Distinct observed road-user support | road users; availability rule below |
| $N_{\mathrm{obs}}(C,I)$ | Observation-contribution count | observations |
| $N_{\mathrm{exp}},N_{\mathrm{meas}},N_{\mathrm{unavail}},N_{\mathrm{miss}}$ | Expected/measured/unavailable/missing sample counts | scheduled observation opportunities |
| $\bar n(C,I)$ | Mean sampled occupancy | road users per measured sample |
| $v_m(b;t)$ | Measured value of metric m at evaluation time t | metric-specific |
| $\Theta_a(C)$ | Effective application requirements for C | metric bounds and provenance |
| $\underline\theta_m^{(a)}(C),\overline\theta_m^{(a)}(C)$ | Effective lower/upper bound for metric m | same units as v_m |
| $\mathcal T_D,\mathcal T_P^{(a)}$ | Data quadtree; application Policy Tree | separate structures |
| $\pi$ | Adaptation action-selection strategy | mapping from private decision state to action |
| $Q_i=(F_i,J_i)$ | Fixed application query, footprint and query interval | independent of chosen output cells/windows |
| $y_i,\widehat y_i$ | Reference query answer; reconstructed public answer | query-specific; occupancy uses road users |
| $\bot$ | Undefined/unavailable value | never silently replaced with zero |

Reserve phi for realized motion as requested. Use d for tree depth, not l, because ell is
reserved for l-diversity. Use delta_sigma for sampling, Delta_b for aggregation duration and
an explicitly named age/delay for freshness. Do not use one `dt` symbol for all three.
Use a for the application; h(C) for cell side; alpha for an action if an action variable is
needed. The Policy Tree is T_P^(a), not pi; pi denotes the action order. Epsilon/delta privacy
budgets and noisy-output symbols are introduced only with an actual corresponding mechanism.

Rendered mathematical notation for the principal geometry is:

$$
\Omega\subset\mathbb R^2,\quad u\in\mathcal U_{\mathrm{all}},\quad
\phi_u:t\mapsto\mathbf x_u(t),\quad
b=(C_b,I_b),\quad I_b=[t_b^-,t_b^+).
$$

The symbol table uses LaTeX directly. Plain-text aliases in prose/code mappings are search
aids, not additional symbols. A trajectory is defined over its road user's lifetime;
$\mathcal U_{\mathrm{GT}}(t)$ contains the road users present in the GT state at time t.

## 4. Geometry, cell IDs and semantic regions

**G1 — Quadtree geometry.** For square coverage of side L:

$$
h(C)=L\,2^{-d(C)},\qquad A(C)=h(C)^2,\qquad 1\le d(C)\le D.
$$

The synthetic depth-zero root describes Omega but is not a supported data aggregation cell
in the current implementation. Depth-one data cells have IDs 12–15; the policy tree has a
synthetic depth-zero root. For quadrant q in {0,1,2,3}:

$$
\nu(C_{\mathrm{child},q})=4\nu(C)+q,\qquad
\nu(\operatorname{parent}(C))=\lfloor\nu(C)/4\rfloor.
$$

The parent identity is a representable data cell only when its depth is at least one.
The ID starts with binary `11`, followed by two bits per quadrant. The x/east bit contributes
1; the y/south bit contributes 2, consistent with the screen-coordinate convention. Given
the stream origin, L and depth convention, the ID determines geometry; an ID alone does
not carry a global coordinate system or metre scale.

Example: L=80 m and D=6 gives h_leaf=1.25 m. A minimum allowed search depth of 1 limits
coarsening to 40-m cells, not the full 80-m synthetic root. Three upward levels multiply
side by 8 and area by 64; they do not require 64 materialized bucket copies.

A functional region R_r need not equal a data cell. It can span or intersect many cells.
Currently its boundaries must align to finest-cell edges, and selected regions are disjoint
axis-aligned rectangles. General polygon/overlap semantics require an explicit future
geometry compiler. “Not one-to-one with cells” must not imply that arbitrary misalignment
is already accepted by the current parser.

## 5. Time and observations

**T1 — Schedule and interval boundaries.** Within one declared sampling schedule:

$$
t_j=j\delta_\sigma\ (j\ge1),\qquad
\mathcal J(I)=\{j\ge1:t_j\in I\},\qquad N_{\mathrm{exp}}(I)=|\mathcal J(I)|.
$$

GT state exists at t=0, but there is no scheduled sensor measurement batch at t=0 in this aggregation-input
baseline. A sample exactly at t_b^+ belongs to the following interval. At 100-ms sampling,
[0,1000) has nine scheduled samples; [1000,2000) has ten. Sensor initialization/internal
velocity history is distinct from this output schedule.

Implementation clocks are integer simulation milliseconds. Spatial quantities use metres;
velocity uses m/s, requiring explicit conversion if divided by millisecond differences.
Renderer FPS, simulation steps, sensor sampling and aggregation duration are separate.
Wall-clock processing time must be named and measured independently.

For a measured batch, an internal cell observation provides road-user ID, class and finest
observed cell. A mathematical observation record does not automatically include GT position.
Membership o in O(C,I) is determined by its observed cell being a descendant of C and its
time lying in I. This preserves the distinction between measurement and private GT.

**T2 — Observation coverage.** Each scheduled sample is measured, explicitly unavailable,
or missing because no batch was received:

$$
N_{\mathrm{exp}}=N_{\mathrm{meas}}+N_{\mathrm{unavail}}+N_{\mathrm{miss}},\qquad
\operatorname{Complete}(I)\iff N_{\mathrm{exp}}>0\ \land\ N_{\mathrm{meas}}=N_{\mathrm{exp}}.
$$

A measured-empty batch contributes one to N_meas and zero to N_obs. Missing and unavailable
batches never establish empty occupancy. Coverage refers to this sensor observation
schedule and declared footprint, not proof that a physical sensor detected every human.

## 6. Count and occupancy definitions

**M1 — Contributions, identity support and sampled occupancy.**

$$
N_{\mathrm{obs}}(C,I)=|\mathcal O(C,I)|,\qquad
\mathcal U(C,I)=\bigcup_{o\in\mathcal O(C,I)}\{\operatorname{uid}(o)\}.
$$

$$
\begin{aligned}
n(C,I)&=
\begin{cases}|\mathcal U(C,I)|,&N_{\mathrm{meas}}(I)>0,\\\bot,&N_{\mathrm{meas}}(I)=0,\end{cases}\\
\bar n(C,I)&=
\begin{cases}\dfrac{N_{\mathrm{obs}}(C,I)}{N_{\mathrm{meas}}(I)},&N_{\mathrm{meas}}(I)>0,\\\bot,&N_{\mathrm{meas}}(I)=0.\end{cases}
\end{aligned}
$$

Here uid(o) is the internal road-user identity, not a cell ID.
The underlying union can be empty even with no measurements, but the reported support
metric is unavailable then. With measured-empty evidence n=0 is a defined observed value.
N_obs is always an observation count, including zero with no received contributions.
bar n is a discrete sample mean, not a continuous-time integral or the distinct union count.
Repeated observations of one ID increase N_obs, not n. Current per-type counts count
observation contributions; they are not distinct-person sensitive-attribute histograms.

**M2 — Other implemented scalar metrics.**

$$
\Delta_b=t_b^+-t_b^-,\quad
A_{\mathrm{eval}}(b;t)=t-t_b^-,\quad
D_{\mathrm{post}}(b;t)=t-t_b^+,\quad
c_{\mathrm{meas}}(I)=N_{\mathrm{meas}}/N_{\mathrm{exp}}\quad(N_{\mathrm{exp}}>0).
$$

The evaluator also provides h(C) and A(C). A_eval is a conservative interval age, not the
exact age of every observation. A simulated sealing age is A_seal=t_seal-t_b^-; the public
`sealed_at_ms` is a sealing timestamp, not the instant a recipient actually receives data.
Network/persistence wall-clock latency is not derived from these simulation-clock formulas.

## 7. Region-induced requirements and candidate eligibility

**P1 — Applicable regions.** For selected regions of application a:

$$
\mathcal I_a(C)=\{r:\operatorname{area}(C\cap R_r)>0\}.
$$

Touching a boundary without positive-area overlap does not add a region requirement.
Let S_a(C) contain the application-root requirement source plus the type and instance
sources for all r in I_a(C). The root always applies, including outside selected regions.
For the union M_a(C) of required metric IDs, intersect their bounds:

$$
\underline\theta_m^{(a)}(C)=\max_{\eta\in\mathcal S_a(C)}\underline\theta_{m,\eta}^{(a)},\qquad
\overline\theta_m^{(a)}(C)=\min_{\eta\in\mathcal S_a(C)}\overline\theta_{m,\eta}^{(a)}.
$$

A missing lower/upper bound is mathematically -infinity/+infinity; actual configured bounds
remain finite and use the registered domain. A weaker child requirement cannot relax an
inherited bound. A cross-region footprint can have an empty admissible range while its
children remain individually feasible. The current parser rejects an inherited conflict
within one region at startup; a conflicting combined footprint is a failed candidate.

**P2 — Admissibility of a cell/interval candidate.** For valid geometry and stream context:

$$
\operatorname{Admissible}_a(b;t)=
\operatorname{Complete}(I_b)\ \land\
\bigwedge_{m\in\mathcal M_a(C_b)}
\left[v_m(b;t)\ne\bot\ \land\
\underline\theta_m^{(a)}(C_b)\le v_m(b;t)\le\overline\theta_m^{(a)}(C_b)\right].
$$

Bounds are inclusive. Every required metric must be available; a configured occupancy-MAE
requirement cannot pass online while the reference input is absent. This Boolean predicate
expresses eligibility. Diagnostics additionally preserve `pass`, `fail`, `unavailable` and
`not_configured`; those statuses must not be conflated. With no configured policy there
is no policy-approved publication decision.

The whole-footprint rule includes empty portions of C. It does not clip C to a road strip,
weight rules by overlap area or forbid crossing functional-region boundaries. An aggregate
cell still represents its whole quadtree square. Such alternative semantics need an explicit
new model and implementation.

## 8. Cell windows and coordination

A region supplies bounds on I_b. It does not supply I_b itself. Even two cells entirely
inside the same region may reach their required support at different times.

| Candidate cell | Applicable region | Example duration bound | Possible future local interval |
|---|---|---:|---|
| C_1 | Carriageway | 200 ms | [0,200) |
| C_2 | Footway | 1000 ms | [0,400) |
| C_3 | The same footway | 1000 ms | [0,800) |

These intervals illustrate the implemented cell-local model; exact observed intervals depend
on the configured checks, input and coordination holds. A parent overlapping road and footway inherits the 200-ms upper bound, so it cannot
simply absorb the whole 800-ms footway candidate.

Current common-window model:

$$
I_{C,h}=I_h\quad\text{for every selected cell in terminal decision }h.
$$

The controller also takes a conservative whole-grid duration/age cap, including empty
regional footprints. Terminal decisions hand over at a common boundary. The history can
query cell-local intervals; the opt-in local controller now schedules and retires independently
completing cells/coordination groups. A coordination group may couple
cells across a semantic boundary or several cells inside one region.

## 9. Spatial and temporal transformations

**A1 — Spatial merge.** A parent candidate covers the complete parent footprint and one
shared interval I. It is reconstructed from all child support, including measured-empty
parts, and reassessed under the parent's effective requirements:

$$
\mathcal U(P,I)=\bigcup_{C\in\operatorname{children}(P)}\mathcal U(C,I),\qquad
N_{\mathrm{obs}}(P,I)=\sum_{C\in\operatorname{children}(P)}N_{\mathrm{obs}}(C,I).
$$

Distinct support is generally not additive. Counts of observations are additive over these
disjoint child footprints. The proposed parent replaces all sibling choices together;
current capped failure can suppress passing siblings too. Selective child rescue is A07.

Different child windows cannot be concatenated into a parent and treated as one common
window. A future coordinator must reconstruct a valid parent interval from complete retained
history, respect every applicable bound, and avoid overlap with reserved/published support.
It can align future unpublished support when available; historical publication cannot be
undone by deleting a database row.

**A2 — Temporal extension.** Keep C and t_b^- fixed and increase t_b^+ in declared steps.
For disjoint adjacent intervals I_1 and I_2:

$$
\mathcal U(C,I_1\cup I_2)=\mathcal U(C,I_1)\cup\mathcal U(C,I_2),\qquad
\bar n(C,I_1\cup I_2)=
\frac{N_{\mathrm{obs}}(C,I_1)+N_{\mathrm{obs}}(C,I_2)}
{N_{\mathrm{meas}}(I_1)+N_{\mathrm{meas}}(I_2)}
$$

when the denominator is positive. Never average interval means without their sample-count
weights. Extending time can raise identity support but need not improve every metric.

**A3 — Split / refinement.** Select finer descendants for new unpublished support in a
later decision. It does not restore detail that was absent from an earlier public aggregate
or rewrite an earlier release. Distinguish observation-tree refinement from changing the
selected publication cut.

## 10. Buckets, strategy and lifecycle

A logical bucket key is beta=(nu,d,t^-,generation) inside stream context zeta. It records
end, maximum extension end, retention deadline and role. Region ID is not part of the key.
A bucket can refer to a leaf or a representable ancestor. Private alternatives may overlap
without constituting multiple public disclosures.

- **Active:** the logical record for a current aggregation choice.
- **Preemptive:** a private alternative for possible coarser/longer support.
- **Collecting / Closed:** observation-progress states. Closed means the watermark reached
  the requested end; it does not imply complete measurements, passed privacy checks or release.
- **Terminal decision:** stop adapting this interval and release eligible support or retire
  it with suppression. A deadline is not a claim that privacy passed.
- **Reserved / sealed / committed / retired:** publication lifecycle, governed separately
  from bucket observation progress. Use the exact stage rather than an ambiguous “finished”.

The bucket API and role metadata are implemented/tested. The current adaptive controller
queries shared history on demand; it does not autonomously materialize active/preemptive
records for every cell or maintain an eager ancestor cache. Do not equate conceptual bucket
roles with a fully implemented precomputation algorithm.

Canonical strategy names identify the dimension to preserve:

| Strategy | Priority | Action order after a failing finest candidate |
|---|---|---|
| Temporal First | Temporal detail/freshness | Try spatial aggregation, then extend time when needed and permitted. |
| Spatial First | Spatial detail | Try temporal extension, then spatial aggregation at the bound/deadline/final flush. |

Both first assess the finest candidate, permit early successful completion and enforce all
hard bounds. pi denotes this deterministic action rule; it is not a learned RL policy,
a formal optimizer or the Policy Tree itself. Execution strategy is currently application-
root-level. Numeric region constraints are resolved separately for each candidate cell.

## 11. Publication geometry and scope of guarantees

For one interval, a publication cut K is an antichain of data nodes with nonoverlapping
footprints. It can be partial: unoccupied and suppressed cells need not appear publicly.
A private terminal diagnostic cut additionally accounts for suppressed observed support;
it is not necessarily a full partition of Omega either.

**R1 — No overlapping public support within one stream.** For distinct public blocks b_i,b_j:

$$
\operatorname{area}(C_i\cap C_j)=0\quad\lor\quad |I_i\cap I_j|=0.
$$

This is a rule about cell/time support within one run/sensor/application. It does not prevent
the same road-user identity contributing at different times, establish privacy across a
trajectory, or justify joint release across several applications. Policy-compliant output
is not automatically formally anonymous. The current private-final-snapshot coordinator
reserves and retires the whole common interval; its release document holds multiple cells
sharing that interval. Per-cell-window publication is not yet that document's contract.

Release soundness, contribution conservation, bounded attempts, feasibility and optimality
are different claims. The first properties have implementation checks and regression
coverage; a formal proof and independent completeness/optimality study are separate work.
No output means no evidence of useful availability; undefined compliance/MAE denominators
must not be converted into favorable zero/100% scores.

## 12. Fixed-query utility

Let Q_i=(F_i,J_i) be an application query whose footprint and interval are fixed before
comparing aggregation methods. F_i is neither a functional region by definition nor the
method's chosen data cell. It may be designed to lie in a functional region. Define its
scheduled sample indices J(J_i) by T1.

**U1 — Reference occupancy.** With complete private reference evidence:

$$
y_i=\frac{1}{|\mathcal J(J_i)|}
\sum_{j\in\mathcal J(J_i)}\sum_{u\in\mathcal U_{\mathrm{GT}}(t_j)}
\mathbf1\{\phi_u(t_j)\in F_i\}.
$$

The existing ideal-sensor replay uses coordinates at those sample times as its reference;
incomplete reference support makes y_i unavailable. A physical noisy-sensor study needs
separate GT and observation contracts. True occupancy and observed support are distinct.

For reconstruction, only public blocks are used. Define uniform spatial allocation and
constant occupancy within each released interval. At a scheduled time in a query:

$$
\widehat n_i(t_j)=
\sum_{b\,\mathrm{public}:\ t_j\in I_b}
\bar n_b\,\frac{\operatorname{area}(F_i\cap C_b)}{A(C_b)},\qquad
\widehat y_i=\frac{1}{|\mathcal J(J_i)|}\sum_{j\in\mathcal J(J_i)}\widehat n_i(t_j).
$$

The estimate is defined only when released cells with available means cover all of F_i at
every scheduled query sample. The displayed sum over partial support must not be used to
fill an uncovered remainder with zero. This reconstruction is an explicit estimate, not
recovered original positions. Default queries are regular 10-m cells and full 1-s intervals; the controlled
coordination study also declares 5-m / 200-ms queries. Fixed rectangular reporting masks
select fully contained query footprints; arbitrary query geometries need an extension. A trailing partial query interval is excluded.

**U2 — Denominators and conditional error.** Let $\mathcal Q$ be the index set of all fixed
queries $Q_i$. Let $\mathcal Q_{\mathrm{ans}}$ contain the answered indices,
$\mathcal Q_{\mathrm{ref}}$ the reference-available indices, and
$\mathcal Q_{\mathrm{score}}=\mathcal Q_{\mathrm{ans}}\cap\mathcal Q_{\mathrm{ref}}$:

$$
c_{\mathrm{ans}}=\frac{|\mathcal Q_{\mathrm{ans}}|}{|\mathcal Q|},\qquad
c_{\mathrm{score}}=\frac{|\mathcal Q_{\mathrm{score}}|}{|\mathcal Q|},\qquad
\operatorname{MAE}_{\mathrm{occ}}=
\frac{1}{|\mathcal Q_{\mathrm{score}}|}\sum_{i\in\mathcal Q_{\mathrm{score}}}|\widehat y_i-y_i|.
$$

MAE is undefined when Q_score is empty. Coverage is undefined with no reference queries.
The coverage denominator includes empty reference cells. Query availability and measured
sample fraction are different quantities. Report common-query error as an additional
comparison with its own support count, never as a replacement for full-domain coverage.

Observation retention is the sum of released observation contributions divided by input
contributions on the same finite horizon. It is undefined with no input contributions and
is not a privacy score or a substitute for application-query coverage.

## 13. Privacy terminology and pending contracts

Use k_sup^(a)(C) for the operational `distinct_contributors.min` requirement:

$$
n(C,I)\ge k_{\mathrm{sup}}^{(a)}(C).
$$

Reserve **k-anonymity** for a declared protected record/entity and public QI mapping.
For a representation with one record per protected entity in the chosen analysis unit,
let $Q_{\mathrm{id}}$ map an entity to its released QI tuple. Define nonempty groups:

$$
\begin{aligned}
E_{\mathbf q}&=\{u\in\mathcal U_{\mathrm{rel}}:Q_{\mathrm{id}}(u)=\mathbf q\},\\
k_{\min}&=\min_{\mathbf q:E_{\mathbf q}\ne\varnothing}|E_{\mathbf q}|,\\
\ell_{\min}^{\mathrm{distinct}}&=\min_{\mathbf q:E_{\mathbf q}\ne\varnothing}|\{S_u:u\in E_{\mathbf q}\}|.
\end{aligned}
$$

Here $\mathcal U_{\mathrm{rel}}$ is the represented entity set and $S_u$ is the declared
sensitive attribute. Both minima are undefined with no released groups. Repeated-window,
trip-based and whole-trajectory representations need explicit grouping/protection contracts.

These are future representation-specific evaluation definitions, not implemented current
online guarantees. They do not automatically apply to the aggregate count release schema.
Other l-diversity variants require different definitions. Missing sensitive values must
not be counted as an extra protective category without an explicit missing-data contract. Every distribution must specify
whether its units are people, trips or repeated observations. Entropy of traffic mix alone
is not attacker uncertainty. No average local support replaces the required minimum bound.
The original definitions are given by
[Sweeney](https://dataprivacylab.org/dataprivacy/projects/kanonymity/kanonymity.pdf) and
[Machanavajjhala et al.](https://www.cs.cornell.edu/johannes/papers/2006/2006-icde-publishing.pdf).

Exact/generalized location, time, class or direction can play QI/secret roles only under a
specified public view and attacker knowledge. A latent trip purpose or destination label
requires a meaningful assignment model. Pending attribute/attack contracts remain separate
from the current utility/policy milestone; see [PRIVACY_EVALUATION.md](PRIVACY_EVALUATION.md).

## 14. Code-to-model mapping

| Mathematical / scientific concept | Current implementation |
|---|---|
| Stream context zeta | `AggregationConfig.runId`, `sensorId`, `applicationId` |
| Omega, D | `GridCoverage`; `leafDepth` |
| C, nu, d, h | `CellGeometry`; `historyCell`; `historyAncestor` |
| R_r, semantic type | `Region.id`, `type`, `area`; adapted to `PolicyRegion` |
| T_P^(a), Theta_a(C) | `PolicyTree`, `resolve`, `EffectiveMetricPolicy` |
| Metric definition / bounds / value | `MetricDefinition`, `MetricRequirement`, `MetricValue` |
| O_sigma,j | `ObservationBatch`; `observedAtMs`, `status`, `observations` |
| Internal ID and class of observation | `CellObservation.contributorId`, `type` |
| I_b, Delta_b | `startMs`, `endMs`; `window_duration_ms` |
| N_obs | `observationContributions`; metric `observation_contributions` |
| n | `distinctContributors`; metric `distinct_contributors`; replay public field `distinct_road_users` |
| bar n | `meanSampleOccupancy`; metric `mean_sample_occupancy` |
| h, A | `cell_side_m`, `cell_area_m2` |
| A_eval, D_post | `age_at_evaluation_ms`, `post_window_delay_ms` |
| N_meas/N_exp | `measured_sample_fraction` |
| B_beta | `CandidateBucket`, `BucketKey`; stream scope supplied by the owning history |
| Shared history / reconstruct candidate | `AggregationHistory::query`, `queryFinest`, `queryBucket` |
| Spatial cut proposal | `SpatialSelector::propose`; `SpatialSelection` |
| pi / current common interval | `AdaptiveAggregation`, `TemporalAdaptationConfig`, private `Pending` |
| Publication / reservation / retirement | `PublicationCoordinator`, `ReleaseSnapshot`, `PublicationState` |
| GT phi / planned P_u | Actual GT positions over time / `Agent::trajectory` waypoint vector |
| Fixed-query y, y_hat, MAE | `tools/evaluation/occupancy.py`; online `occupancy_mae` stays unavailable |

Legacy code names containing “contributor” or “agent” remain valid API/schema identifiers.
Use “distinct road-user support”, “road-user observations” and “mean sampled occupancy” in
new figures and prose. Renaming a schema is a separate compatibility change, not part of
this terminology update.

## 15. Language and publication checklist

Use: “cell-local windows under region-induced constraints”; “coordinated sibling merge”;
“coarsening to an ancestor”; “refinement for subsequent unpublished support”; “complete
measured observation coverage”; “conditional occupancy MAE and answered-query coverage”.

Avoid: “a region aggregates”; “one bucket per region”; “region and quadtree cell are the
same”; “larger depth means larger cell”; “sum of distinct counts”; “closed means released”;
“empty means suppressed”; “frame rate means aggregation duration”; “k-anonymity is average
cell occupancy”; “Policy Tree computes the metrics”; “Privacy-Driven is an implemented
optimizer”. Use “minimum/maximum cell side” instead of the ambiguous “minimum resolution”.

Before using a new metric/model in presentation, paper or dissertation, record:

1. Symbol, plain-English term, units, protected/statistical unit and code/schema mapping.
2. Required inputs, reference, weighting, interval/boundary and unavailable cases.
3. Whether it is a metric, requirement, strategy, lifecycle state or experimental outcome.
4. Whether it is implemented, a mathematical definition, an untested hypothesis or a target.
5. The actual evidence and the scope of any proof/experimental statement.

Change this canonical reference first when adopting new terminology; reconcile active
cross-references and figure labels in the same documentation change. Preserve older dated
experimental artifacts as evidence, with their old labels traceable through the mapping.

## 16. LaTeX reuse

[`notation/ump_equations.tex`](notation/ump_equations.tex) is an exact generated export of
the display equations in this reference. It contains equations only; use the definitions,
units, assumptions and implementation-status statements above with them. Include it in
article or Beamer source after loading `amsmath` and `amssymb`, or select the equations
needed by one slide.

Regenerate from the repository root after changing this reference:

```sh
python3 tools/export_notation.py
python3 tools/export_notation.py --check
```

The Markdown reference is authoritative; the fragment must not be edited by hand.

## 17. Planned environment and demand vocabulary

These terms support scenario design; they do not imply an implemented environment, demand
engine or routing stack. See [FUNCTIONAL_REGIONS_AND_EVIDENCE.md](FUNCTIONAL_REGIONS_AND_EVIDENCE.md).

| Term | Meaning | Distinction |
|---|---|---|
| Canonical environment geometry | Source geometry and stable entity IDs for physical features | Preserved independently of the chosen data-grid depth. |
| Map topology / connectivity | Allowed connections between surfaces, portals and places | Not identical to geometric adjacency or quadtree parent/child topology. |
| Derived spatial discretization | A grid/index/mask derived from source geometry | Used for spatial lookup; distinct from adaptive release aggregation. |
| Portal | An entrance, exit or crossing connection with movement meaning | A point/segment need not be a positive-area policy region. |
| Destination | A selected place/portal that a road user intends to reach | A behavioral choice, not an output cell. |
| Demand | Configured arrival/departure/visit process | Not inferred from a static map alone. |
| Realized flow / flux | Crossing events per declared duration at a specified portal/boundary | Counts events, not necessarily distinct people, and is not occupancy. |
| Dwell time | Duration of an explicitly defined visit/activity | Not automatically the time an ID is absent from a sensor. |
| Global route | Intended connected sequence through the environment | May generate the planned waypoint path P_u. |
| Local motion / trajectory generation | Short-horizon execution of that route | Produces realized phi_u(t) under motion/interaction rules. |
| Collision avoidance | Local interaction handling subject to clearance/motion rules | Distinct from global route selection and policy-driven aggregation. |

Reserve $\lambda_e^{\mathrm{in}}(t)$ for a future configured arrival intensity at portal e
(events/s), and $f_e^{\mathrm{in}}(I)$ for realized entry-crossing flow on interval I. With
the current millisecond convention, its definition is
$f_e^{\mathrm{in}}(I)=N_e^{\mathrm{in}}(I)/(|I|/1000)$ for a positive-duration interval.
Use analogous outward quantities only after defining their activity/stock model. This
notation does not select a Poisson process or implement an online flow metric. Counting
repeated crossings differs from n(C,I), which counts an identity once per cell/window.


## 18. Empirical source-contribution membership

Implemented evaluation contract: [EMPIRICAL_PRIVACY_IMPLEMENTATION.md](EMPIRICAL_PRIVACY_IMPLEMENTATION.md).
Use source-contribution membership for inclusion in the mechanism input, including targets
whose observations are eventually suppressed. It does not mean physical presence or
survival in a public output. The unit is one road user's whole recorded contribution over
the declared horizon. Candidate auxiliary trace knowledge is the same in IN and OUT.

Let s be the frozen attack score, tau its calibration-selected decision threshold, and
TP/FP/TN/FN the held-out confusion counts for membership. Predict IN when s >= tau.

$$
\operatorname{TPR}=\frac{TP}{TP+FN},\qquad
\operatorname{FPR}=\frac{FP}{FP+TN},\qquad
\operatorname{Adv}_{\tau}=\operatorname{TPR}-\operatorname{FPR}.
$$

$$
\operatorname{BA}_{\tau}=\frac{\operatorname{TPR}+1-\operatorname{FPR}}{2}.
$$

With n_in IN scores and n_out OUT scores, the tie-aware empirical ranking measure is

$$
\widehat{\operatorname{AUC}}=
\frac{1}{n_{\mathrm{in}}n_{\mathrm{out}}}
\sum_{i=1}^{n_{\mathrm{in}}}\sum_{j=1}^{n_{\mathrm{out}}}
\left(\mathbf{1}[s_i^{\mathrm{in}}>s_j^{\mathrm{out}}]
+\frac{1}{2}\mathbf{1}[s_i^{\mathrm{in}}=s_j^{\mathrm{out}}]\right).
$$

Undefined denominators remain unavailable. The implemented balanced game has membership
prior 0.5. Deployment precision requires a separately declared prior; balanced accuracy
alone does not supply it. ROC-AUC and threshold advantage are attack outcomes, not formal
k-anonymity/DP parameters or a universal privacy score. AUC below 0.5 is not test-inverted.
The independent source realization is the uncertainty unit, with both labels and all
mechanisms paired; the present bootstrap preserves scenario strata and freezes fitted
models/thresholds. The calibrated FPR cap is empirical, not a held-out guarantee.


## 19. Cell-local ownership and retirement

The private ownership frontier at time t is a spatial partition. Each member owns its
original unresolved interval start; functional regions supply constraints without owning
these intervals. Write rho_C(t) for the retirement frontier of cell C. Its open interval
starts there, even if source history retains earlier observations.

$$
\mathcal F(t)=\{(C,s_C,e_C,d_C)\},\qquad s_C=\rho_C(t).
$$

Here e_C is the next planned check and d_C the absolute policy/global deadline. Cells may
have different e_C and d_C. A parent P can directly take over the same unpublished prefix
of a complete mixed-depth descendant frontier D_P:

$$
P=\mathop{\dot\bigcup}_{C\in\mathcal D_P}C,\qquad
s_C=s\ \ (C\in\mathcal D_P),\qquad I=[s,e).
$$

Metrics are recomputed from the retained observations in P x I. Equal check endpoints
are unnecessary. If starts differ because some support has retired, a historical parent
cannot reuse that support; resolve earlier prefixes and establish a future common boundary.
No equation here assumes that extending time or coarsening space improves every metric.

For completed terminal decisions H over a fully finalized run [0,T), including private
suppression and measured-empty retirement, exact ownership requires:

$$
\sum_{h\in\mathcal H}\mathbf 1_{C_h}(x)\mathbf 1_{[s_h,e_h)}(t)=1,
\qquad x\in\Omega,\quad 0\le t<T.
$$

For the recipient stream, only selected decisions remain; the sum is at most one. These
are support/accounting invariants, not a privacy guarantee or an optimality theorem.

## 20. Contribution retention, exact age and paired evaluation

Version 1.2 adds the measurement contract used by the October 19 common/local study.
Let O_in be the finite collection of input observation occurrences and B_pub the
recipient-visible released blocks. Each occurrence o has sensor position x(o) and
observation time t(o). Define the retained subcollection by exact point/time membership:

$$
\mathcal O_{\mathrm{ret}}=
\{o\in\mathcal O_{\mathrm{in}}:\exists b\in\mathcal B_{\mathrm{pub}},\quad
\mathbf x(o)\in C_b\ \land\ t(o)\in I_b\},\qquad
r_{\mathrm{obs}}=\frac{|\mathcal O_{\mathrm{ret}}|}{|\mathcal O_{\mathrm{in}}|}.
$$

The denominator must be positive. These are observation occurrences, not distinct
road users. Regional diagnostics filter actual source points by the declared fixed
reporting mask; they do not allocate a coarse cell count uniformly. This is private
source-based evaluation, separate from public-only occupancy reconstruction.

Nonoverlap makes the containing public block b(o) unique. With sealing timestamp
t_seal(b), define exact simulated observation age and its retained-only mean:

$$
A_{\mathrm{obs}}(o)=t_{\mathrm{seal}}(b(o))-t(o),\qquad
\overline A_{\mathrm{obs}}=
\frac{1}{|\mathcal O_{\mathrm{ret}}|}\sum_{o\in\mathcal O_{\mathrm{ret}}}A_{\mathrm{obs}}(o).
$$

The mean is undefined if no observations were retained. A_obs is distinct from the
interval-age envelope A_seal(b)=t_seal(b)-t_b^- in Section 6; it does not reuse a, the
application identifier. Public timing uses N_obs(C_b,I_b) as its weight for duration,
interval-age envelope and post-window delay. It is invariant to grouping the same
blocks into more release documents. Exact age and retention use the private source.
None of these simulation-clock quantities measures wall-clock delivery latency.

For nonnegative values z_i and positive contribution weights w_i, the reported weighted
quantile is the smallest observed value reaching the cumulative proportion p:

$$
q_p=\min\left\{z:\sum_{i:z_i\le z}w_i\ge p\sum_iw_i\right\},\qquad 0<p\le1.
$$

Zero-weight rows have no influence. With no positive weight the distribution is
undefined. In the exact-age histogram w_i counts retained occurrences at that age;
in public timing it is the released cell's observation-contribution count.

For one frozen realization and preservation strategy, let Q_pair be the fixed queries
scored by both common and local coordination. Use the same reference answers:

$$
\mathcal Q_{\mathrm{pair}}=\mathcal Q_{\mathrm{score}}^{\mathrm{com}}
\cap\mathcal Q_{\mathrm{score}}^{\mathrm{loc}},\qquad
\operatorname{MAE}_{\mathrm{pair}}^{\mathrm{loc}}=
\frac{1}{|\mathcal Q_{\mathrm{pair}}|}\sum_{i\in\mathcal Q_{\mathrm{pair}}}
|\widehat y_i^{\mathrm{loc}}-y_i|.
$$

The common expression substitutes com for loc. Both are undefined with no paired
queries. Report full-domain coverage alongside paired accuracy; removing unanswered
queries is not an improvement in availability. For every declared scalar evaluation
metric M, use Delta_M=M_loc-M_com for the paired difference. The independent complete
realization is the statistical unit. Different windows, queries, strategies and
execution repeats from that realization do not increase its replication count.

Actual contracts and formulas map to `occupancy.summarize_region_retention`,
`occupancy.summarize_queries`, `coordination_metrics.summarize` and
`run_coordination_study.matched_errors`. See [the study](COORDINATION_STUDY_2026-10-19.md)
for the two fixed query scales, full/interior boundaries, defined sample counts,
retained-set age conditioning and the limits of the synthetic evidence.


## 21. Causal endpoint rescue cut

For one current closed endpoint, freeze the unresolved owner assessments and effective
policies before any release. For each nonempty failed owner f, let r(f) be its nearest
passing proper ancestor with compatible common unpublished support and a permitted
spatial action. Owners without such an ancestor contribute no proposal. Spatial First
retains temporal priority until the candidate's deadline pressure permits fallback.

$$
\mathcal A=\{r(f):r(f)\ \text{exists}\},\qquad
\mathcal P=\{C\in\mathcal A:\nexists C'\in\mathcal A\ \text{with}\ C\subsetneq C'\}.
$$

Data-quadtree cells are disjoint or nested. Therefore two different members of P cannot
overlap: otherwise one would be a strict subset of the other and would not belong to P.
This proves the planned cut's spatial nonoverlap at that endpoint, assuming the existing
quadtree geometry contract. It does not prove asynchronous completeness, minimum error,
maximum retained support over future intervals, or privacy. Disjoint finer rescues remain
fine; a larger passing ancestor is not proposed solely because it passes.

Each accepted cell still requires complete source coverage, exact metric recomputation,
all effective requirements and an unreused space-time domain. Holds require an actual
compatible ancestor with possible future geometry/time bounds; future passing observations
are not assumed. See [the refined implementation and experiments](COORDINATION_REFINEMENT_2026-10-19.md).
