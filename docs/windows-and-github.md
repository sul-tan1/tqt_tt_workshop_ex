# Windows tools and GitHub Actions

This project uses the Windows OSS CAD Suite for local simulation, synthesis, and
waveform viewing. GitHub's Ubuntu runners build the Sky130 chip layout with
LibreLane and run the physical checks. Installing the Windows archive does not
change what is installed on GitHub's runners.

## Run on this computer

Open this repository folder in VS Code (`tqt_tt_workshop_ex`, the folder containing
`info.yaml`), then open a PowerShell terminal:

```powershell
cd C:\Users\Shot\Downloads\tapeoutproject\tqt_tt_workshop_ex
.\tt.cmd doctor
.\tt.cmd test
.\tt.cmd synth
.\tt.cmd wave
```

- `doctor` checks the tools and checks that `info.yaml` and `test/Makefile` list the same sources.
- `test` runs the existing cocotb test: all 2,048 combinations of A, B, and opcode, including output flags and the bidirectional pin controls.
- `synth` runs Yosys and writes a generic synthesized netlist and log to `build/synth/`. The GitHub `gds` job produces the Sky130 layout.
- `wave` opens `test/tb.fst` in GTKWave using the saved signal selection in `test/tb.gtkw`.
- `viewer` opens the published chip layout in your browser, once the GitHub `viewer` job has succeeded.

In VS Code, **Terminal > Run Task** offers the same test, synthesis, and viewing
commands. These tasks are for Windows. The existing Linux Makefile and dev
container remain available for Linux work.

### Setup again or on another Windows computer

Download the Windows x64 archive from the
[official OSS CAD Suite releases](https://github.com/YosysHQ/oss-cad-suite-build/releases),
then run:

```powershell
.\tt.cmd setup -Archive 'C:\path\to\oss-cad-suite-windows-x64-20261120.tgz'
```

On this machine, the default archive path is already configured, so `.\tt.cmd setup`
is enough. Setup extracts the suite under `.tools/oss-cad-suite` and downloads a
portable CPython 3.11.9 runtime plus the cocotb dependencies into `.tools/python`.
The separate CPython runtime supports the published Windows cocotb wheels; the
suite's bundled Python is a MinGW build. All these files stay inside the project.
Setup needs internet access for Python and PyPI downloads. Later tests run locally.

The launcher activates the suite for its own process. It passes a process-scoped
PowerShell execution-policy option, so it also works with Windows' default script
policy. It does not change your global PATH or persistent PowerShell policy.

For an already extracted suite elsewhere, set its path before running setup:

```powershell
$env:OSS_CAD_SUITE = 'C:\tools\oss-cad-suite'
.\tt.cmd setup
```

The local runner supplies Icarus' backend location explicitly because this Windows
build otherwise looks for `/yosyshq/lib/ivl`. It also disables vvp's default
short-path discovery and uses explicit VPI module paths. Use `tt.cmd test` to
include those fixes.

## Enable GitHub once

These settings belong to the fork, not the workshop's original repository:

1. Open [your repository's Actions tab](https://github.com/sul-tan1/tqt_tt_workshop_ex/actions).
   If GitHub displays a message that workflows are disabled in this fork, enable them.
2. Open [Settings > Actions > General](https://github.com/sul-tan1/tqt_tt_workshop_ex/settings/actions).
   Make sure the policy permits the actions referenced in `.github/workflows/`, including
   TinyTapeout and the helper actions they use. The normal permissive setting works
   for a personal workshop fork. Organization policies may require an administrator.
3. Open [Settings > Pages](https://github.com/sul-tan1/tqt_tt_workshop_ex/settings/pages).
   Under **Build and deployment**, set **Source** to **GitHub Actions**.
   Do this before starting the first layout build. Do not create a separate Pages
   workflow; the existing `viewer` job deploys the site.
4. If the `github-pages` environment has branch restrictions, allow the branch you
   are building. The workflow gives the viewer `pages: write` and `id-token: write`;
   the build jobs use `contents: read`.

GitHub Pages availability depends on repository visibility and plan. Public
repositories can use it on GitHub Free; see
[GitHub's Pages workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
The Pages source setting is also documented in the
[Tiny Tapeout FAQ](https://tinytapeout.com/faq/#my-github-action-is-failing-on-the-pages-part).

## What happens on every push

The current workflows have `push` and `workflow_dispatch` triggers. Push a commit
to GitHub and you should see three workflow runs: `test`, `gds`, and `docs`.

| Workflow/job | When it runs | What it does / where to look |
| --- | --- | --- |
| `test` / `test` | Every push, or manually | Runs the exhaustive RTL cocotb test. Download `test-results` for `tb.fst` and `results.xml`. |
| `gds` / `gds` | Every push, or manually | Uses `TinyTapeout/tt-gds-action@ttsky26d`, LibreLane, and `sky130A` to produce the physical design. Artifacts include `tt_submission`, `GDS_logs`, and `gds_render`. |
| `gds` / `precheck` | After `gds` succeeds | Runs Tiny Tapeout's physical submission checks using the generated layout. Read this job's log for any failed check. |
| `gds` / `gl_test` | After `gds` succeeds | Downloads the generated netlist and matching PDK, then runs `test/test.py` through `test/Makefile` with `GATES=yes`. Waveforms/results are in `gatelevel_test_results`. |
| `gds` / `viewer` | After `gds` succeeds | Publishes the layout through GitHub Pages and adds 3D viewer, Explorer, and 2D preview links to the run summary. |
| `docs` / `docs` | Every push, or manually | Builds the project documentation from `info.yaml` and `docs/info.md`. |
| `fpga` / `fpga` | Manually by default | Builds for the TT ASIC Sim ICE40UP5K hardware. It is optional for the ASIC build. |

`precheck`, `gl_test`, and `viewer` run independently after the `gds` job. If `gds`
fails, those jobs are skipped. A working viewer does not prove that the physical
checks or gate-level test passed: check all four jobs. The separate RTL `test`
workflow also needs to pass.

The FPGA workflow's `branches: none` filter excludes ordinary pushes. To run it,
choose **Actions > fpga > Run workflow**. If you want FPGA builds on every push,
remove that branch-filter line in `.github/workflows/fpga.yaml`.

The upstream [GDS action](https://github.com/TinyTapeout/tt-gds-action/blob/ttsky26d/action.yml),
[gate-level action](https://github.com/TinyTapeout/tt-gds-action/blob/ttsky26d/gl_test/action.yml),
and [viewer action](https://github.com/TinyTapeout/tt-gds-action/blob/ttsky26d/viewer/action.yml)
define these tools, artifact names, and viewer links. Keep all the TinyTapeout
actions on the workshop's matching `ttsky26d` version.

### Make a push or start a run manually

For future edits, use VS Code Source Control to stage, commit, and push, or:

```powershell
git status
git add README.md docs .github .vscode scripts tt.cmd .gitignore test info.yaml
git commit -m "Set up Windows CAD tools and project workflow guide"
git push origin main
```

Review the staged changes before committing. `.tools/`, `build/`, waveforms, and
simulation outputs are ignored and must stay out of GitHub.

To build an already-pushed commit without making another edit: open **Actions**,
select **gds**, choose **Run workflow**, select `main`, then click **Run workflow**.
Run `test` and `docs` the same way if needed. A local commit alone does not trigger
GitHub Actions; it must reach the GitHub repository.

## Open the visualizations

There are two different kinds of view:

- **Signals over time:** run `.\tt.cmd test`, then `.\tt.cmd wave`. In GTKWave,
  use **Zoom > Zoom Best Fit** to see the whole test, expand `tb.user_project`,
  and select signals. `ui_in[3:0]` is A, `ui_in[7:4]` is B, and `uio_in[2:0]`
  is the opcode. `uo_out[3:0]` is the result; bits 4, 5, 6, and 7 are carry,
  zero, negative, and signed overflow. Opcodes 0–7 are ADD, SUB, AND, OR, XOR,
  CMP, shift left by one, and shift right by one. The recommended Surfer VS Code
  extension can also open the FST file directly.
- **The manufactured chip layout:** after a successful `viewer` job, open the
  `gds` run's **Summary** and click **Open 3D viewer** or **Open in Tiny Tapeout
  Explorer**. You can also run `.\tt.cmd viewer` or open
  [the project's Pages site](https://sul-tan1.github.io/tqt_tt_workshop_ex/).
  The site is created by a successful deployment; it can return 404 before that.

To inspect a GitHub waveform locally, download and unzip `test-results` or
`gatelevel_test_results`, then run:

```powershell
.\tt.cmd wave -Waveform 'C:\path\to\unzipped\tb.fst'
```

## Common failures

| Symptom | Next step |
| --- | --- |
| No workflows start after a push | Confirm the commit reached `origin`, open the fork's Actions tab, enable workflows, and check Actions policy. A pending/queued run has started but is waiting for a runner. |
| `precheck`, `gl_test`, and `viewer` are skipped | Open the failed `gds` job first. |
| `viewer` fails to deploy or Pages returns 404 | Set Pages Source to GitHub Actions, check the `github-pages` environment's branch rules, then start a **new** `gds` run. |
| Viewer reports multiple `github-pages` artifacts | Use **Run workflow** for a fresh `gds` run instead of rerunning only the failed viewer job. This is covered in the [Tiny Tapeout FAQ](https://tinytapeout.com/faq/#my-viewer-job-fails-after-enabling-github-pages-and-rerunning-it-on-an-existing-gds-action). |
| Missing module or source file | Keep `info.yaml`'s `top_module` equal to `tt_um_alu_4bit` and include every source in both `info.yaml` and `test/Makefile`. Update `test/tb.v` if you rename the top module. |
| RTL passes but `gl_test` fails | Read its simulation log and waveform. The shared test waits 100 ns per input vector to allow gate delays to settle. Check the implementation and pin connections if values still differ. |
| GDS lint, routing, timing, or precheck fails | Read the first failing step and `GDS_logs`. Local Yosys success alone does not validate timing, layout, DRC, or LVS. |
| Action cannot resolve `ttsky26d` | Confirm the workshop's required template version before changing all action refs together. Installing a different local suite does not resolve an action-ref error. |
| `wave` cannot find `tb.fst` | Run `.\tt.cmd test` successfully first or pass the downloaded waveform path. |

## Optional: gate-level simulation and hardening locally

For native Windows gate-level simulation, obtain the netlist from the successful
`tt_submission` artifact, save it as `test/gate_level_netlist.v`, and provide an
extracted Sky130 PDK matching that artifact's `pdk.json`:

```powershell
$env:PDK_ROOT = 'C:\path\to\pdk'
# Must contain sky130A\libs.ref\sky130_fd_sc_hd\verilog\...
.\tt.cmd gl-test
.\tt.cmd wave
```

The Windows archive does not include the Sky130 PDK or the complete LibreLane ASIC
flow. For local GDS and physical checks, follow the official
[Tiny Tapeout local hardening guide](https://tinytapeout.com/guides/local-hardening/)
using the Linux dev container or WSL2/Linux environment. In VS Code the existing
`.devcontainer/` config is available through **Dev Containers: Reopen in Container**;
Docker Desktop must be running with its Linux backend. Local hardening downloads
additional tools and PDK data. The Linux shell uses `make` in `test/`, while Windows
uses `tt.cmd`. The GitHub path above needs neither local Docker nor a local PDK.
