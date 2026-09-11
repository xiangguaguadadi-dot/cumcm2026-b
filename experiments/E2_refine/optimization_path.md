# E2 optimization path

R1 examined five deployed variants from S1, with one unexecuted exact-parent packaging snapshot. The current accepted component is **r1_station_only**.

- No opportunity sensing: rejected (quick +20.830, new development +16.691 s/source).
- Task-cost gate only at opportunity stops: rejected (+0.594 / +0.971).
- Task-cost gate at opportunity and known-source station revisits: completed 4800, Q4 467.405184, all complete.
- Preserve S1 opportunity sensing, gate only known-source station revisits: current best, 4800 Q4 466.842681; Q3 unchanged 235.876946.
- Skip station retests only when radius<=20: controlled simpler alternative, development -1.843 versus -7.129 for the full station cost gate; not promoted to full.

Independent source development uses 96 new mixed-Q4 cases, shared between controlled variants; quick/full/old-final are already exposed. R1 does not claim a travel saving: on development movement increased 0.281 s/source while nonmovement decreased 7.410. Remaining hypotheses are not declared saturated.


R2 tested two source-service units. Same-location certified clear had no development benefit (465.060460 vs R1 465.036237); rejected. One persistent original service-loop round then global replanning gave 457.721499865727 on4800 exposed cases, allcomplete, Q3 unchanged. OwnR1 decrease 9.121181599098 s/source. Both distinct controls retained.
