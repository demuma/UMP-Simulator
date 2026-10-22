# Privacy attributes, environmental context and the online evaluation contract

Date: 2026-10-20. Status: research and interface contract, updated after the completed
causal-prefix study and logical deadline utility. Source-membership attacks and causal
logical-time replay are implemented. Semantic-visit inference and an instrumented live
recipient service remain separate future experiments. This document adds no map importer,
visit generator, online client, release mechanism or sensitive-attribute metric.

Read alongside [the notation contract](TERMINOLOGY_AND_NOTATION.md),
[the empirical membership implementation](EMPIRICAL_PRIVACY_IMPLEMENTATION.md),
[the coordination/privacy assessment](PRIVACY_COORDINATION_STUDY_2026-10-19.md) and
[the completed causal-prefix report](CAUSAL_PRIVACY_REPORT_2026-10-20.md).
The [causal implementation](CAUSAL_PRIVACY_IMPLEMENTATION.md),
[predeclared protocol](CAUSAL_PRIVACY_PROTOCOL_2026-10-20.md) and
[test report](CAUSAL_PRIVACY_TEST_REPORT_2026-10-20.md) define the completed logical-time boundary.
Use the notation contract for established symbols; in particular, $\phi_u(t)$ denotes
the realized position trajectory of road user $u$.

## Attribute roles depend on the experiment

A quasi-identifier (QI) is an attribute or combination useful for linking observations
to a person or distinguishing that person's records with declared external knowledge.
A sensitive attribute (SA) is the fact the experiment aims to protect from inference.
The same field can play both roles in different experiments. Removing a person's name
does not remove linkage through other attributes. This is the motivation of the
original [k-anonymity model, Sweeney (2002)](https://dataprivacylab.org/dataprivacy/projects/kanonymity/kanonymity.pdf).

It is reasonable to treat every informative attribute as a *candidate* linkage feature
when designing a threat model. It is imprecise to declare every attribute automatically
a QI: a constant field supplies no discrimination, a private field absent from every
recipient channel supplies no direct observation, and an unknown attribute cannot be
assumed to be matching external knowledge. Derived combinations and correlations can
still create exposure. State the observable channels, population, available knowledge
and matching precision rather than assigning a permanent QI/SA flag to each column.

The following table is a proposed UMP classification for explicitly declared observers.
It is a research design, not a claim that every field is already released or simulated.

| Information | Possible linkage role | Possible protected fact | UMP treatment |
|---|---|---|---|
| Internal road-user ID | Persistent linkage across raw observations; identifying if an external mapping exists | Source participation or linkage to a named person | Private research identity; exclude from recipient exports and attack features. A random ID alone does not establish anonymity. |
| Road-user type or movement mode | Can narrow a candidate set when an observer knows that a person cycles or drives | A person's transport mode, if that is the declared secret | The privacy-fixture generator uses pedestrian/bicycle/car labels; it bypasses the live simulator taxonomy. These synthetic movement classes are not an already justified sensitive category. |
| Timestamp or visit schedule | Links an observed event to an external sighting or known routine | Attendance at a place or time | Declare timestamp precision, uncertainty and permissible knowledge intervals. |
| Cell ID, position and cell size | Cell ID implies public location and scale; combinations with time can support matching | A person's location or route | Public aggregate geometry is observable, although individual positions are not recipient records. Include adaptive geometry in the attack surface. |
| Realized trajectory $\phi_u$ | Several observations can narrow candidate trajectories | Unobserved route segment, source membership or destination | Current auxiliary knowledge is sampled candidate positions; it is not a named-person reidentification benchmark. |
| POI category and visit event | A known visit can link a person to observations near that location | Whether the person entered a declared destination category | Requires an explicit semantic map and an entry/dwell event, not a proximity label alone. |
| Home/work location or regular routine | External address/routine knowledge can anchor linkage | Residence, workplace or routine itself | Not currently generated as a defensible ground-truth attribute; introduce only with a separate generative/observation contract. |
| Release counts, geometry and logical sealing times | Adaptive decisions may provide evidence about a candidate's contribution | Membership or a future semantic secret | Already part of the recipient attack surface. Debug reasons, suppressed candidates and private journals are excluded. |

A hospital-adjacent observation is not evidence of diagnosis: a person may be passing,
working, delivering goods or accompanying someone. Even an actual hospital visit is a
visit label, not a medical diagnosis. A future synthetic diagnosis-inference experiment
would need a justified probabilistic relationship and its own truth labels; it must
not manufacture a diagnosis directly from a map category.

## What the current privacy experiment measures

The current protected unit is a candidate's recorded source contribution over the
whole declared horizon. The secret is whether that contribution was included. The
candidate physically exists in both worlds; OUT removes its source observations,
while every background observation and sampling opportunity remains fixed.

The longer-horizon robustness extension retains that membership question. Its noisy
candidate observations model uncertain auxiliary knowledge, and its independent
background-density test cohort examines one specified distribution shift. Longer
paths and a nonlinear classifier strengthen the assessment within that contract; they
do not introduce sensitive visits, named-person linkage or realistic city semantics.

The October 20 causal-prefix extension keeps exactly this whole-source secret over a
fixed 16-second horizon. It evaluates six declared recipient looks on fresh independent
groups. Whole releases become visible at logical sealing; candidate sightings are selected
with per-timestamp Bernoulli probability 0.25 and become usable only after both acquisition
and reported time. The recent and cumulative views share the same causally acquired
auxiliary knowledge. No withheld sensitive visit, map semantics or different membership
unit is introduced after observing earlier attack results.

The completed study does not establish a general privacy benefit from the history
representation: all 16 local history-minus-recent AUC intervals include zero. These are
pointwise conditional intervals, not an equivalence result. At the first look, recent and
cumulative public records coincide, and history duplicates their feature block; logistic
regression's effective L2 penalty on that public block can be halved without extra information.
The contrast therefore includes representation/fitting effects. An unrestricted observer
can ignore extra coordinates, so a lower fitted history AUC is not improved privacy from
receiving more data. A matched redundant-block control would be a separate follow-up.

Environmental structure can matter before a full city model exists. A known walkway,
entrance or obstacle can rule out possible paths, while land use can turn a geometric
observation into contextual evidence. Which effect occurs depends on what the observer
knows and what is actually released. The empirical finding that mobility traces can
be highly distinctive motivates testing such knowledge. The well-known four-point,
95% result belongs to the particular mobile-phone dataset and resolution studied by
[de Montjoye et al. (2013)](https://doi.org/10.1038/srep01376); it is neither a UMP result
nor a transferable success rate for sparse aggregate releases.

A simple synthetic environment with labeled destinations and valid access paths is
sufficient for a first controlled visit experiment. A large real-map importer is not
a prerequisite. Real maps are a later validity improvement, together with realistic
flows, routes and observations; they do not automatically make an attack realistic.

## Local support is not formal k-anonymity or l-diversity

The implemented distinct-road-user threshold is an operational release constraint.
It counts distinct contributing identities in a candidate cell/time support. It does
not prove that a recipient cannot distinguish an individual using auxiliary knowledge,
multiple releases or adaptive geometry.

For a person-level table with an explicitly defined QI projection $Q$, an equivalence
class can be written as

$$
E_Q(r)=\{r' : Q(r')=Q(r)\}.
$$

A table-level k-anonymity check requires $|E_Q(r)|\ge k$ for every released record,
under that representation and the assumptions of the linking model. Repeated samples
of one person must not silently count as several protected people. A stream of count
aggregates is not this table; a cell's support count cannot be substituted for the
QI-equivalence-class size.

For a specified sensitive value $s_u$ and an appropriate person-level equivalence
class, a simple *distinct-l-diversity* check asks for at least $\ell$ distinct sensitive
values. This is only one variant: it does not by itself control skew, semantic similarity
or every background-knowledge attack. The original
[l-diversity paper, Machanavajjhala et al. (ICDE 2006)](https://www.cs.cornell.edu/johannes/papers/2006/2006-icde-publishing.pdf)
explains why k-anonymity alone can still permit sensitive-attribute disclosure.

Consequently, adding an `ell` policy field or counting movement-mode categories would
not establish l-diversity protection. First define the sensitive secret, protected
unit, table/equivalence relation and observer, then specify exactly which diversity
statistic is enforced and evaluate inference under the resulting releases. Membership
attacks remain meaningful even when no sensitive attribute has been defined.

## Proposed semantic-visit experiment

This is a separate, optional next dataset and inference game. It must not be reported
as an extension of source-membership labels without changing the contract.

1. Define a small immutable public environment: destination footprints and entrances,
   permitted access paths, category labels and ambiguity rules. Keep the same map in
   both worlds. Begin with synthetic categories such as destination A/B; introduce
   health, religion or other sensitive interpretations only if justified explicitly.
2. Define one protected candidate and a hidden interval $I$. Its source contribution
   exists in both worlds. A private label $S\in\{0,1\}$ selects whether it visits the
   designated destination during $I$, using feasible routes with controlled arrival,
   dwell and departure schedules. A visit requires a declared entry/dwell event;
   passing the building does not suffice. Background observations remain fixed.
3. Make the candidate's publicly known prefix and suffix identical across the worlds
   wherever feasible, including a guard interval around the hidden branch. If a suffix,
   arrival time or total movement already reveals the visit, disclose that leakage in
   the auxiliary-knowledge baseline rather than attributing it to the aggregator.
4. Freeze the observer's public map, route/dynamics knowledge, timestamp/position
   uncertainty and candidate observations outside $I$. The withheld interval and any
   guard interval must be declared before generation. Do not give the attacker the
   secret trajectory segment, destination label or a proxy such as a private scenario
   identifier. Labels and full traces remain evaluator-only.
5. Generate independent background/target realizations. Keep both secret worlds, all
   mechanisms, all noise profiles and every fragment of a trajectory in the same
   train/calibration/test group. Reject identity-renamed clones. For a generalization
   claim, additionally hold out destination instances or map layouts; report this
   separately from a same-map test.
6. Predeclare label prevalence, visit/dwell rules, target selection, horizon, mechanisms,
   attack families and observable inputs. Train on training groups and choose
   thresholds on calibration groups. Freeze them before ordinary and shifted test
   evaluation. Preserve existing completed membership test sets.
7. Report auxiliary-knowledge-only, release-plus-knowledge and no-output controls;
   attack AUC and calibrated TPR/FPR; empirical precision under declared visit priors;
   and uncertainty over independent groups. Report utility/availability beside attack
   outcomes. Balanced labels do not establish real-world prevalence or precision.

The comparison asks how much the recipient release helps infer a particular visit
beyond its declared auxiliary knowledge. It does not infer a medical condition,
establish a universal privacy guarantee or identify a named person merely because a
visit classifier succeeds.

## Online recipient-prefix contract

Earlier membership attacks inspect the complete final recipient transcript. The
completed October 20 study now evaluates causal recipient prefixes offline, using a
fixed public clock and an explicit logical availability assumption. A live application
must additionally establish actual receipt. At logical time $t$, define

$$
\mathcal V_{\le t}
 =\{r : t^{\mathrm{available}}_r\le t\},\qquad
s_t=\operatorname{Attack}(\mathcal V_{\le t},\mathcal K_{\le t},M),
$$

where $r$ is a public release, $t^{\mathrm{available}}_r$ is its recipient-availability
time, $\mathcal K_{\le t}$ contains only then-permitted auxiliary knowledge, and $M$ is the
declared public mechanism/environment description. A model may be trained offline,
but every test-time feature must come from this prefix. Prohibit future releases,
future candidate observations, private bucket state and full-run statistics used to
normalize a prefix. Reveal a fixed public horizon only if the recipient actually
knows it in advance.

The implemented replay study assumes instantaneous delivery and sets
$t^{\mathrm{available}}_r=\texttt{sealed\_at\_ms}$. Complete immutable records are selected
at that boundary; neither counts nor source intervals are clipped to a checkpoint.
The six looks are 1000, 2000, 4000, 8000, 12000 and 16000 ms. Recent releases arrive in
$(t-1000,t]$; the history view retains earlier releases as well. The final look includes
EOF behavior and is distinguished from interior checkpoints.

Each checkpoint model is fitted on TRAIN only. Each predeclared stream/view/profile/family
strategy calibrates one threshold on CAL candidates' maximum scores over all six looks,
then freezes it for both independent TEST cohorts. First-alarm TPR/FPR keep the paired source-group denominator; six looks are not
six independent opportunities at FPR 0.1. The empirical CAL cap is neither a TEST FPR cap
nor a deployment guarantee. Report observed TEST false alarms, the balanced evaluation
prior and pointwise grouped uncertainty. Failed bounded attacks do not prove formal
protection or rule out other families, features or observation schedules.

This measures a logical-time system under its assumption. `sealed_at_ms` alone is not
evidence of actual recipient receipt or a wall-clock latency measurement. Transport delays,
failures and schedules still require separate observations or a declared model. The prefix
study is not an implemented online service or an online privacy-enforcement mechanism.

Prefix checkpoints and application query deadlines are fixed before outcomes. The
completed study reports attack scores/first-alarm curves at the declared looks and,
separately, occupancy availability/error at each query's own deadline. It uses 10-m/1-s
queries with 0/200/500/1000-ms lags. The primary cohort contains query ends from 1 through
14 seconds so every declared lag remains strictly before EOF. Boundary queries are
separate; deadlines after the horizon are censored instead of counted as misses.

A query requires complete released spatial support at every scheduled source sample.
Unknown/absent sparse output is not zero; explicit released zero is usable. A late
aggregate cannot retrospectively repair a missed deadline. The default study reports
per-lag utility, rather than additional utility checkpoint curves; a tested helper can
summarize only then-due query deadlines. Changing an application's accepted lag changes
the evaluation, not the published stream or an attacker's access, and supplies no causal
privacy/latency mechanism frontier.

A period without releases remains part of the recipient view when a public clock is
known. An observer may save every earlier release: later database deletion cannot retract
information it already received.

Use a concrete application, such as occupancy for a specified road region, with a
fixed query footprint, time window, acceptable error and delivery deadline. Utility
must reflect that task. Evidence from crowdsourcing systems illustrates why location-
only distortion can fail to describe the actual measurement/application utility:
[Boukoros et al., USENIX Security 2019](https://www.usenix.org/conference/usenixsecurity19/presentation/boukoros).
That finding motivates choosing a UMP task; it does not establish performance of the
present traffic application.

Measure three separate quantities in any future online prototype:

| Quantity | Required observation | Interpretation |
|---|---|---|
| Logical interval, sealing age and simulated post-window delay | Source sample time, interval bounds and logical sealing time | Policy/aggregation behavior in simulation time. |
| Controller processing cost | Monotonic wall-clock timestamps around a precisely specified operation | Computational cost on the measured hardware, including only declared work. |
| End-to-end availability and deadline misses | Wall-clock capture/submission and actual recipient receipt, with a declared clock relation | What the application can use and when; includes configured transport/storage/client work. |

A simulator speedup above one does not prove a bounded per-update deadline or low
end-to-end latency. Report tail processing times, queue/backlog behavior, deadline
misses, workload size, hardware and output availability. For multiple application
streams, predeclare whether one observer sees one stream or their union; independent
per-application policy satisfaction does not establish protection against combined
views.

## Implementation boundary and next decision

Robustness, causal public-prefix replay and deadline-aware occupancy scoring are now
implemented and evaluated without infrastructure semantics. Their completed reports
retain the whole-source inclusion secret and the logical availability assumption. They
do not supply a sensitive-visit result, a calibrated live privacy guard or a formal
privacy guarantee.

The optional semantic milestone still needs the explicit visit-event/hidden-interval
contract above, a feasible environment and an auxiliary-knowledge-only baseline before
renderer or route-planning detail. It is a separate secret and dataset, not a replacement
membership label chosen because an earlier privacy contrast was inconclusive. Existing
membership test sets remain frozen.

A future live application must instrument capture, processing, queues, storage and
recipient receipt before claiming end-to-end latency or real-time deadline compliance.
The completed logical-time evaluation is a foundation for that work, not evidence that
its transport, wall-clock behavior or multi-application privacy is already validated.
