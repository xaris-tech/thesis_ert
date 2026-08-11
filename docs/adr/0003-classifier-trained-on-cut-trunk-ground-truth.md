# Classifier is trained and evaluated on cut-trunk ground truth, not on standing trees

The standing-tree field study yields expert labels but no operator-controlled ground truth, and its sample count is unknown in advance. The cut-trunk pilots yield the opposite: every defect stage and drilled sector is a fact the operator created. Running an identical four-stage ladder on several trunks, with both drive patterns and three repeats per stage, produces roughly 72 labelled scans carrying two independent ground-truth labels — severity stage and drilled sector. The classifier is therefore trained and evaluated there, using leave-one-trunk-out cross-validation so that reported scores reflect performance on a trunk never seen in training. Standing-tree scans are reported descriptively and are not fed to the trained model, because a model fitted to drilled holes in cut wood has no established relationship to disease in living tissue.

Each scan is reduced to roughly 10-20 physically interpretable summary features rather than its 216 raw transfer resistances, and fitted with logistic regression or a shallow decision tree. With 72 samples, using the full raw vector would give three times more features than samples and would fit noise; a flexible model on all features would most likely learn trunk identity rather than defect state.

## Considered Options

- **Pipeline definition with no model fitted** — what the methodology draft currently promises, on the premise that only three trees exist. That premise no longer holds for the bench, so the concession is unnecessary.
- **Train on trunks, then predict standing trees** — completes the end-to-end story but invites challenge on any tree prediction.
- **Random forest or gradient boosting on all features** — standard and easy, but with 72 samples from a handful of trunks it would likely key on trunk identity.

## Consequences

- `docs/chapter-3-methodology-draft.md` §3.13 and §3.14 are out of date: they assume a fixed three-tree study and a classifier that is defined but never fitted.
- Feature selection becomes real design work, since each of the 10-20 features must have a physical meaning that can be defended.
- Any dimensionality reduction or scaling must be fitted inside each cross-validation fold, not before splitting.
- The thesis can report an evaluated classification system without ever claiming disease diagnosis.
