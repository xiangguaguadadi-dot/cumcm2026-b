# Q4 structure preregistration

The experiment tests two distinct structural claims on the unchanged C7 solver.

1. **Known-count stopping certificate.** Because source channels are distinct and the stated source count is at most 16, observing 16 distinct source channels proves all remaining unobserved channels absent. Compare C7's enabled certificate with the identical solver configured with `upper_bound_stop=False` on the same worlds.
2. **Continuous antenna-heading certificate.** After a successful clear, the clear coordinate is within 20 m of the source. Each earlier positive receive site restricts a directional emitter's heading to a widened semicircle. Intersect those continuous arcs. A directional truth must remain inside; an empty intersection certifies an omnidirectional source under the stated model.

Primary gate: all paired tasks complete, mean count-stop minus no-stop seconds/source below zero, and the 5,000-resample world bootstrap upper 95% bound below zero. Heading safety gate: no directional true heading excluded. Report omni precision/recall and interval widths regardless of outcome.

Frozen-v1 full worlds are exposed regression evidence. The constructed 16-source suite is pressure evidence. Neither is blind or official Windows evidence. Truth is read only by the post-run auditor.
