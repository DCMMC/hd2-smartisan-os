# Smartisan debug evidence

These files document the Smartisan OS port only. Earlier records can describe failed experiments or superseded states; the current result is summarized in the repository README and `release/BUILD-STATUS.json`.

Network identifiers, credentials, raw framebuffer buffers, device backups, user data and keys are excluded. The phone clock was unset and reports 2014-05-20 in many logs; host capture names and monotonic times establish sequence. Final hardware evidence is in `smartisan-alpha2-hardware-validation.json`; animation measurements are in `smartisan-animation-performance-validation.json` and `icon-flip-v10/`.

`WORKSPACE-AUDIT.json` inventories the public text records recovered during the final comparison with the original porting workspace. It includes the previously omitted keyguard and power-policy patch reports, resolution/performance measurements, power-key tests and the later Smartisan boot capture. Download logs, raw framebuffer data, transient UI dumps and shared SD-card repair history remain excluded.
