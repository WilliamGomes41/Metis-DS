-------------------------- MODULE MetisAnnotation --------------------------
EXTENDS Naturals, Integers, FiniteSets
CONSTANTS Required, EnforceFence, EnforceReview
VARIABLES phase, selected, revision, overview, seal, job, built, approved,
          policy, ingestChoice, release, active
vars == <<phase, selected, revision, overview, seal, job, built, approved,
          policy, ingestChoice, release, active>>
Phases == {"received", "extracting", "source_error", "annotating", "overview",
           "building", "build_error", "review", "ready", "published", "withdrawn"}
Init ==
  /\ phase = "received" /\ selected = {} /\ revision = 0
  /\ overview = -1 /\ seal = -1 /\ job = -1 /\ built = -1
  /\ approved = {} /\ policy \in SUBSET Required /\ "r1" \in policy /\ ingestChoice = policy /\ release = -1 /\ active = FALSE
PrepareSource ==
  /\ phase = "received" /\ phase' = "extracting"
  /\ UNCHANGED <<selected, revision, overview, seal, job, built, approved, policy, ingestChoice, release, active>>
SourceReady ==
  /\ phase = "extracting" /\ phase' = "annotating"
  /\ UNCHANGED <<selected, revision, overview, seal, job, built, approved, policy, ingestChoice, release, active>>
SourceFailed ==
  /\ phase = "extracting" /\ phase' = "source_error"
  /\ UNCHANGED <<selected, revision, overview, seal, job, built, approved, policy, ingestChoice, release, active>>
RetrySource ==
  /\ phase = "source_error" /\ phase' = "extracting"
  /\ UNCHANGED <<selected, revision, overview, seal, job, built, approved, policy, ingestChoice, release, active>>
SaveSelection ==
  /\ phase = "annotating" /\ revision < 4
  /\ \E i \in {1, 2} \ selected : selected' = selected \cup {i}
  /\ revision' = revision + 1
  /\ UNCHANGED <<phase, overview, seal, job, built, approved, policy, ingestChoice, release, active>>
OpenOverview ==
  /\ phase = "annotating" /\ phase' = "overview" /\ overview' = revision
  /\ UNCHANGED <<selected, revision, seal, job, built, approved, policy, ingestChoice, release, active>>
ReturnToSelections ==
  /\ phase = "overview" /\ phase' = "annotating"
  /\ UNCHANGED <<selected, revision, overview, seal, job, built, approved, policy, ingestChoice, release, active>>
SealAndBuild ==
  /\ phase = "overview" /\ selected = {1, 2} /\ overview = revision
  /\ phase' = "building" /\ seal' = revision /\ job' = revision
  /\ built' = -1 /\ approved' = {}
  /\ UNCHANGED <<selected, revision, overview, policy, ingestChoice, release, active>>
BuildFailed ==
  /\ phase = "building" /\ phase' = "build_error"
  /\ UNCHANGED <<selected, revision, overview, seal, job, built, approved, policy, ingestChoice, release, active>>
RetryBuild ==
  /\ phase = "build_error" /\ phase' = "building"
  /\ UNCHANGED <<selected, revision, overview, seal, job, built, approved, policy, ingestChoice, release, active>>
EditSelection ==
  /\ phase \in {"building", "review", "ready"} /\ revision < 3
  /\ phase' = "annotating" /\ selected' = {1}
  /\ revision' = revision + 1 /\ built' = -1 /\ approved' = {}
  /\ UNCHANGED <<overview, seal, job, policy, ingestChoice, release, active>>
ActivateBuild ==
  /\ phase \in {"building", "annotating"} /\ job >= 0
  /\ (~EnforceFence \/ (revision = job /\ seal = job /\ selected = {1, 2}))
  /\ phase' = "review" /\ built' = job /\ approved' = {}
  /\ UNCHANGED <<selected, revision, overview, seal, job, policy, ingestChoice, release, active>>
Approve ==
  /\ phase = "review"
  /\ \E r \in policy \ approved :
       /\ approved' = approved \cup {r}
       /\ phase' = IF policy \subseteq approved' THEN "ready" ELSE "review"
  /\ UNCHANGED <<selected, revision, overview, seal, job, built, policy, ingestChoice, release, active>>
Publish ==
  /\ phase \in {"review", "ready"}
  /\ (~EnforceReview \/ (phase = "ready" /\ policy \subseteq approved))
  /\ phase' = "published" /\ release' = built /\ active' = TRUE
  /\ UNCHANGED <<selected, revision, overview, seal, job, built, approved, policy, ingestChoice>>
Withdraw ==
  /\ phase = "published" /\ phase' = "withdrawn" /\ active' = FALSE
  /\ UNCHANGED <<selected, revision, overview, seal, job, built, approved, policy, ingestChoice, release>>
Restart == UNCHANGED vars
Done == phase \in {"published", "withdrawn"} /\ UNCHANGED vars
Next == PrepareSource \/ SourceReady \/ SourceFailed \/ RetrySource
     \/ SaveSelection \/ OpenOverview \/ ReturnToSelections \/ SealAndBuild
     \/ BuildFailed \/ RetryBuild \/ EditSelection \/ ActivateBuild
     \/ Approve \/ Publish \/ Withdraw \/ Restart \/ Done
Spec == Init /\ [][Next]_vars
TypeOK ==
  /\ phase \in Phases /\ selected \subseteq {1, 2} /\ revision \in 0..4
  /\ overview \in -1..4 /\ seal \in -1..4 /\ job \in -1..4
  /\ built \in -1..4 /\ release \in -1..4
  /\ approved \subseteq Required /\ policy \subseteq {"r1", "r2"} /\ ingestChoice \subseteq Required
  /\ active \in BOOLEAN
IngestPolicyPreserved == policy = ingestChoice
OnlySealedSelectionsAreBuilt ==
  phase \in {"review", "ready", "published", "withdrawn"}
  => built = revision /\ built = seal /\ selected = {1, 2}
NoApprovalFromAnnotation ==
  phase \in {"received", "extracting", "source_error", "annotating", "overview", "building", "build_error"}
  => approved = {}
ServingRequiresIngestReview == active => policy \subseteq approved /\ built = revision
WithdrawalStaysInactive == phase = "withdrawn" => ~active
ReleaseIsExact == release >= 0 => release = built /\ phase \in {"published", "withdrawn"}
=============================================================================
