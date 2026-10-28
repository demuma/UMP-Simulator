# Source-type count correction

The immutable declaration-time protocol contains a prose error: it says seven
source road-user types. The frozen canonical configuration and all computations
use **eight terminal source types in a twelve-node taxonomy**:

- Adult Pedestrian
- Child Pedestrian
- Senior Pedestrian
- Pedestrian With Stroller
- Pedestrian With Mobility Aid
- Adult Cyclist
- Senior Cyclist
- Adult E-Scooter Driver

Seven is the number of compared methods per permission condition, not the source
type count. The machine configuration, source recordings, eight-type accounting,
Full111/Scalar31 feature construction, tests and audits were already correct.
No method, source, metric, threshold, model or numerical result is changed by
this correction. The original contract and its hash remain intact; this explicit
correction is published before any new model fit or TEST scoring.
