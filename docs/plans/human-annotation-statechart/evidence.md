# Uitvoer van definitieve pstack-runs

## Hoofdmodel

# MetisAnnotation

TLC reached 80 states and 208 steps. The chart draws 12 states and 19 arrows.
The chart does not draw 112 steps that stay in one chart state.

## Rules that hold
TypeOK, IngestPolicyPreserved, OnlySealedSelectionsAreBuilt, NoApprovalFromAnnotation, ServingRequiresIngestReview, WithdrawalStaysInactive, ReleaseIsExact, NoDeadlock


### TLC op deze configuratie

```text
[0.001s][warning][perf,memops] Cannot use file /tmp/hsperfdata_agent/46 because it is locked by another process (errno = 11)
TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)
Warning: Please run the Java VM which executes TLC with a throughput optimized garbage collector by passing the "-XX:+UseParallelGC" property.
(Use the -nowarning option to disable this warning.)
Running breadth-first search Model-Checking with fp 0 and seed -6783076963079384837 with 1 worker on 9 cores with 2492MB heap and 64MB offheap memory [pid: 46] (Linux 6.18.57 amd64, Debian 21.0.13 x86_64, MSBDiskFPSet, DiskStateQueue).
Parsing file /workspace/scratch/719b891f7b86/metis-statechart/MetisAnnotation.tla
Parsing file /tmp/statechart-lJzeDf/statechart-iVr0Ly/tmp-verdict-1/Naturals.tla
Parsing file /tmp/statechart-lJzeDf/statechart-iVr0Ly/tmp-verdict-1/Integers.tla
Parsing file /tmp/statechart-lJzeDf/statechart-iVr0Ly/tmp-verdict-1/FiniteSets.tla
Parsing file /tmp/statechart-lJzeDf/statechart-iVr0Ly/tmp-verdict-1/Sequences.tla
Semantic processing of module Naturals
Semantic processing of module Integers
Semantic processing of module Sequences
Semantic processing of module FiniteSets
Semantic processing of module MetisAnnotation
Starting... (2026-11-07 18:18:32)
Computing initial states...
Finished computing initial states: 2 distinct states generated at 2026-11-07 18:18:32.
Model checking completed. No error has been found.
  Estimates of the probability that TLC did not check all reachable states
  because two distinct states had the same fingerprint:
  calculated (optimistic):  val = 5.6E-16
210 states generated, 80 distinct states found, 0 states left on queue.
The depth of the complete state graph search is 16.
The average outdegree of the complete state graph is 1 (minimum is 0, the maximum 3 and the 95th percentile is 3).
Finished in 00s at (2026-11-07 18:18:33)


```

## Een reviewer

# MetisAnnotation

TLC reached 38 states and 98 steps. The chart draws 11 states and 16 arrows.
The chart does not draw 54 steps that stay in one chart state.

## Rules that hold
TypeOK, IngestPolicyPreserved, OnlySealedSelectionsAreBuilt, NoApprovalFromAnnotation, ServingRequiresIngestReview, WithdrawalStaysInactive, ReleaseIsExact, NoDeadlock


### TLC op deze configuratie

```text
[0.001s][warning][perf,memops] Cannot use file /tmp/hsperfdata_agent/46 because it is locked by another process (errno = 11)
TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)
Warning: Please run the Java VM which executes TLC with a throughput optimized garbage collector by passing the "-XX:+UseParallelGC" property.
(Use the -nowarning option to disable this warning.)
Running breadth-first search Model-Checking with fp 0 and seed -1398654674715185663 with 1 worker on 9 cores with 2492MB heap and 64MB offheap memory [pid: 46] (Linux 6.18.57 amd64, Debian 21.0.13 x86_64, MSBDiskFPSet, DiskStateQueue).
Parsing file /workspace/scratch/719b891f7b86/metis-statechart/MetisAnnotation.tla
Parsing file /tmp/statechart-1cXg7H/statechart-UbGCUZ/tmp-verdict-1/Naturals.tla
Parsing file /tmp/statechart-1cXg7H/statechart-UbGCUZ/tmp-verdict-1/Integers.tla
Parsing file /tmp/statechart-1cXg7H/statechart-UbGCUZ/tmp-verdict-1/FiniteSets.tla
Parsing file /tmp/statechart-1cXg7H/statechart-UbGCUZ/tmp-verdict-1/Sequences.tla
Semantic processing of module Naturals
Semantic processing of module Integers
Semantic processing of module Sequences
Semantic processing of module FiniteSets
Semantic processing of module MetisAnnotation
Starting... (2026-11-07 18:18:32)
Computing initial states...
Finished computing initial states: 1 distinct state generated at 2026-11-07 18:18:32.
Model checking completed. No error has been found.
  Estimates of the probability that TLC did not check all reachable states
  because two distinct states had the same fingerprint:
  calculated (optimistic):  val = 1.3E-16
99 states generated, 38 distinct states found, 0 states left on queue.
The depth of the complete state graph search is 15.
The average outdegree of the complete state graph is 1 (minimum is 0, the maximum 3 and the 95th percentile is 3).
Finished in 00s at (2026-11-07 18:18:32)


```

## Zonder bouwfence

# MetisAnnotation

TLC reached 130 states and 333 steps. The chart draws 12 states and 21 arrows.
The chart does not draw 180 steps that stay in one chart state.

## OnlySealedSelectionsAreBuilt breaks
The shortest path has 8 steps:
0. Bron ontvangen
1. Voorbereiding starten: Bron voorbereiden
2. Bron beschikbaar: Selecties aanwijzen en opslaan
3. Selectie opslaan: Selecties aanwijzen en opslaan
4. Selectie opslaan: Selecties aanwijzen en opslaan
5. Klaar met dit document: Documentoverzicht controleren
6. Afronden en opbouwen [scope afgehandeld]: Afgeronde selectie opbouwen
7. Bronselectie corrigeren; oordelen vervallen: Selecties aanwijzen en opslaan
8. Verouderde bouw activeren: Beoordeling volgens ingest

## ServingRequiresIngestReview breaks
The shortest path has 10 steps:
0. Bron ontvangen
1. Voorbereiding starten: Bron voorbereiden
2. Bron beschikbaar: Selecties aanwijzen en opslaan
3. Selectie opslaan: Selecties aanwijzen en opslaan
4. Selectie opslaan: Selecties aanwijzen en opslaan
5. Klaar met dit document: Documentoverzicht controleren
6. Afronden en opbouwen [scope afgehandeld]: Afgeronde selectie opbouwen
7. Bronselectie corrigeren; oordelen vervallen: Selecties aanwijzen en opslaan
8. Verouderde bouw activeren: Beoordeling volgens ingest
9. Laatste vereiste oordeel opslaan: Gereed voor publicatie
10. Bevoegd publiceren [ingestbeoordeling compleet]: Gepubliceerd

## Rules that hold
TypeOK, IngestPolicyPreserved, NoApprovalFromAnnotation, WithdrawalStaysInactive, ReleaseIsExact, NoDeadlock


### TLC op deze configuratie

```text
[0.001s][warning][perf,memops] Cannot use file /tmp/hsperfdata_agent/46 because it is locked by another process (errno = 11)
TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)
Warning: Please run the Java VM which executes TLC with a throughput optimized garbage collector by passing the "-XX:+UseParallelGC" property.
(Use the -nowarning option to disable this warning.)
Running breadth-first search Model-Checking with fp 0 and seed 5012391622533424518 with 1 worker on 9 cores with 2492MB heap and 64MB offheap memory [pid: 46] (Linux 6.18.57 amd64, Debian 21.0.13 x86_64, MSBDiskFPSet, DiskStateQueue).
Parsing file /workspace/scratch/719b891f7b86/metis-statechart/MetisAnnotation.tla
Parsing file /tmp/statechart-4hzUWq/statechart-klY8k1/tmp-verdict-1/Naturals.tla
Parsing file /tmp/statechart-4hzUWq/statechart-klY8k1/tmp-verdict-1/Integers.tla
Parsing file /tmp/statechart-4hzUWq/statechart-klY8k1/tmp-verdict-1/FiniteSets.tla
Parsing file /tmp/statechart-4hzUWq/statechart-klY8k1/tmp-verdict-1/Sequences.tla
Semantic processing of module Naturals
Semantic processing of module Integers
Semantic processing of module Sequences
Semantic processing of module FiniteSets
Semantic processing of module MetisAnnotation
Starting... (2026-11-07 18:18:32)
Computing initial states...
Finished computing initial states: 2 distinct states generated at 2026-11-07 18:18:32.
Error: Invariant OnlySealedSelectionsAreBuilt is violated.
Error: The behavior up to this point is:
State 1: <Initial predicate>
/\ revision = 0
/\ overview = -1
/\ approved = {}
/\ seal = -1
/\ active = FALSE
/\ selected = {}
/\ release = -1
/\ policy = {"r1"}
/\ phase = "received"
/\ built = -1
/\ ingestChoice = {"r1"}
/\ job = -1

State 2: <PrepareSource line 15, col 3 to line 16, col 114 of module MetisAnnotation>
/\ revision = 0
/\ overview = -1
/\ approved = {}
/\ seal = -1
/\ active = FALSE
/\ selected = {}
/\ release = -1
/\ policy = {"r1"}
/\ phase = "extracting"
/\ built = -1
/\ ingestChoice = {"r1"}
/\ job = -1

State 3: <SourceReady line 18, col 3 to line 19, col 114 of module MetisAnnotation>
/\ revision = 0
/\ overview = -1
/\ approved = {}
/\ seal = -1
/\ active = FALSE
/\ selected = {}
/\ release = -1
/\ policy = {"r1"}
/\ phase = "annotating"
/\ built = -1
/\ ingestChoice = {"r1"}
/\ job = -1

State 4: <SaveSelection line 27, col 3 to line 30, col 101 of module MetisAnnotation>
/\ revision = 1
/\ overview = -1
/\ approved = {}
/\ seal = -1
/\ active = FALSE
/\ selected = {1}
/\ release = -1
/\ policy = {"r1"}
/\ phase = "annotating"
/\ built = -1
/\ ingestChoice = {"r1"}
/\ job = -1

State 5: <SaveSelection line 27, col 3 to line 30, col 101 of module MetisAnnotation>
/\ revision = 2
/\ overview = -1
/\ approved = {}
/\ seal = -1
/\ active = FALSE
/\ selected = {1, 2}
/\ release = -1
/\ policy = {"r1"}
/\ phase = "annotating"
/\ built = -1
/\ ingestChoice = {"r1"}
/\ job = -1

State 6: <OpenOverview line 32, col 3 to line 33, col 104 of module MetisAnnotation>
/\ revision = 2
/\ overview = 2
/\ approved = {}
/\ seal = -1
/\ active = FALSE
/\ selected = {1, 2}
/\ release = -1
/\ policy = {"r1"}
/\ phase = "overview"
/\ built = -1
/\ ingestChoice = {"r1"}
/\ job = -1

State 7: <SealAndBuild line 38, col 3 to line 41, col 86 of module MetisAnnotation>
/\ revision = 2
/\ overview = 2
/\ approved = {}
/\ seal = 2
/\ active = FALSE
/\ selected = {1, 2}
/\ release = -1
/\ policy = {"r1"}
/\ phase = "building"
/\ built = -1
/\ ingestChoice = {"r1"}
/\ job = 2

State 8: <EditSelection line 49, col 3 to line 52, col 77 of module MetisAnnotation>
/\ revision = 3
/\ overview = 2
/\ approved = {}
/\ seal = 2
/\ active = FALSE
/\ selected = {1}
/\ release = -1
/\ policy = {"r1"}
/\ phase = "annotating"
/\ built = -1
/\ ingestChoice = {"r1"}
/\ job = 2

State 9: <ActivateBuild line 54, col 3 to line 57, col 97 of module MetisAnnotation>
/\ revision = 3
/\ overview = 2
/\ approved = {}
/\ seal = 2
/\ active = FALSE
/\ selected = {1}
/\ release = -1
/\ policy = {"r1"}
/\ phase = "review"
/\ built = 2
/\ ingestChoice = {"r1"}
/\ job = 2

117 states generated, 49 distinct states found, 6 states left on queue.
The depth of the complete state graph search is 9.
The average outdegree of the complete state graph is 1 (minimum is 0, the maximum 3 and the 95th percentile is 3).
Finished in 00s at (2026-11-07 18:18:32)


```

## Zonder reviewgate

# MetisAnnotation

TLC reached 96 states and 256 steps. The chart draws 12 states and 22 arrows.
The chart does not draw 142 steps that stay in one chart state.

## ServingRequiresIngestReview breaks
The shortest path has 8 steps:
0. Bron ontvangen
1. Voorbereiding starten: Bron voorbereiden
2. Bron beschikbaar: Selecties aanwijzen en opslaan
3. Selectie opslaan: Selecties aanwijzen en opslaan
4. Selectie opslaan: Selecties aanwijzen en opslaan
5. Klaar met dit document: Documentoverzicht controleren
6. Afronden en opbouwen [scope afgehandeld]: Afgeronde selectie opbouwen
7. Actuele bouw activeren: Beoordeling volgens ingest
8. Publiceren zonder vereiste oordelen: Gepubliceerd

## Rules that hold
TypeOK, IngestPolicyPreserved, OnlySealedSelectionsAreBuilt, NoApprovalFromAnnotation, WithdrawalStaysInactive, ReleaseIsExact, NoDeadlock


### TLC op deze configuratie

```text
TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)
Warning: Please run the Java VM which executes TLC with a throughput optimized garbage collector by passing the "-XX:+UseParallelGC" property.
(Use the -nowarning option to disable this warning.)
Running breadth-first search Model-Checking with fp 0 and seed 7838605717923842272 with 1 worker on 9 cores with 2492MB heap and 64MB offheap memory [pid: 46] (Linux 6.18.57 amd64, Debian 21.0.13 x86_64, MSBDiskFPSet, DiskStateQueue).
Parsing file /workspace/scratch/719b891f7b86/metis-statechart/MetisAnnotation.tla
Parsing file /tmp/statechart-EtT7vE/statechart-nh8uQL/tmp-verdict-1/Naturals.tla
Parsing file /tmp/statechart-EtT7vE/statechart-nh8uQL/tmp-verdict-1/Integers.tla
Parsing file /tmp/statechart-EtT7vE/statechart-nh8uQL/tmp-verdict-1/FiniteSets.tla
Parsing file /tmp/statechart-EtT7vE/statechart-nh8uQL/tmp-verdict-1/Sequences.tla
Semantic processing of module Naturals
Semantic processing of module Integers
Semantic processing of module Sequences
Semantic processing of module FiniteSets
Semantic processing of module MetisAnnotation
Starting... (2026-11-07 18:18:32)
Computing initial states...
Finished computing initial states: 2 distinct states generated at 2026-11-07 18:18:32.
Error: Invariant ServingRequiresIngestReview is violated.
Error: The behavior up to this point is:
State 1: <Initial predicate>
/\ revision = 0
/\ overview = -1
/\ approved = {}
/\ seal = -1
/\ active = FALSE
/\ selected = {}
/\ release = -1
/\ policy = {"r1"}
/\ phase = "received"
/\ built = -1
/\ ingestChoice = {"r1"}
/\ job = -1

State 2: <PrepareSource line 15, col 3 to line 16, col 114 of module MetisAnnotation>
/\ revision = 0
/\ overview = -1
/\ approved = {}
/\ seal = -1
/\ active = FALSE
/\ selected = {}
/\ release = -1
/\ policy = {"r1"}
/\ phase = "extracting"
/\ built = -1
/\ ingestChoice = {"r1"}
/\ job = -1

State 3: <SourceReady line 18, col 3 to line 19, col 114 of module MetisAnnotation>
/\ revision = 0
/\ overview = -1
/\ approved = {}
/\ seal = -1
/\ active = FALSE
/\ selected = {}
/\ release = -1
/\ policy = {"r1"}
/\ phase = "annotating"
/\ built = -1
/\ ingestChoice = {"r1"}
/\ job = -1

State 4: <SaveSelection line 27, col 3 to line 30, col 101 of module MetisAnnotation>
/\ revision = 1
/\ overview = -1
/\ approved = {}
/\ seal = -1
/\ active = FALSE
/\ selected = {1}
/\ release = -1
/\ policy = {"r1"}
/\ phase = "annotating"
/\ built = -1
/\ ingestChoice = {"r1"}
/\ job = -1

State 5: <SaveSelection line 27, col 3 to line 30, col 101 of module MetisAnnotation>
/\ revision = 2
/\ overview = -1
/\ approved = {}
/\ seal = -1
/\ active = FALSE
/\ selected = {1, 2}
/\ release = -1
/\ policy = {"r1"}
/\ phase = "annotating"
/\ built = -1
/\ ingestChoice = {"r1"}
/\ job = -1

State 6: <OpenOverview line 32, col 3 to line 33, col 104 of module MetisAnnotation>
/\ revision = 2
/\ overview = 2
/\ approved = {}
/\ seal = -1
/\ active = FALSE
/\ selected = {1, 2}
/\ release = -1
/\ policy = {"r1"}
/\ phase = "overview"
/\ built = -1
/\ ingestChoice = {"r1"}
/\ job = -1

State 7: <SealAndBuild line 38, col 3 to line 41, col 86 of module MetisAnnotation>
/\ revision = 2
/\ overview = 2
/\ approved = {}
/\ seal = 2
/\ active = FALSE
/\ selected = {1, 2}
/\ release = -1
/\ policy = {"r1"}
/\ phase = "building"
/\ built = -1
/\ ingestChoice = {"r1"}
/\ job = 2

State 8: <ActivateBuild line 54, col 3 to line 57, col 97 of module MetisAnnotation>
/\ revision = 2
/\ overview = 2
/\ approved = {}
/\ seal = 2
/\ active = FALSE
/\ selected = {1, 2}
/\ release = -1
/\ policy = {"r1"}
/\ phase = "review"
/\ built = 2
/\ ingestChoice = {"r1"}
/\ job = 2

State 9: <Publish line 65, col 3 to line 68, col 97 of module MetisAnnotation>
/\ revision = 2
/\ overview = 2
/\ approved = {}
/\ seal = 2
/\ active = TRUE
/\ selected = {1, 2}
/\ release = 2
/\ policy = {"r1"}
/\ phase = "published"
/\ built = 2
/\ ingestChoice = {"r1"}
/\ job = 2

118 states generated, 50 distinct states found, 6 states left on queue.
The depth of the complete state graph search is 9.
The average outdegree of the complete state graph is 1 (minimum is 0, the maximum 3 and the 95th percentile is 3).
Finished in 00s at (2026-11-07 18:18:32)


```

