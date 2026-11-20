"""Local simulator and synthesis entry points. Uses the same test.py as CI."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / 'test'


def project():
    data = yaml.safe_load((ROOT / 'info.yaml').read_text(encoding='utf-8'))['project']
    top = data['top_module']
    if not re.fullmatch(r'tt_um_[A-Za-z0-9_]+', top):
        raise ValueError(f'Invalid Tiny Tapeout top_module: {top!r}')
    sources = [(ROOT / 'src' / name).resolve() for name in data['source_files']]
    for source in sources:
        if not source.is_relative_to((ROOT / 'src').resolve()) or not source.is_file():
            raise ValueError(f'Missing or invalid source file: {source}')
    # CI still uses the upstream Makefile. Catch a source-list mismatch locally.
    makefile = (TEST / 'Makefile').read_text(encoding='utf-8')
    match = re.search(r'^PROJECT_SOURCES\s*[:?+]?=\s*([^\n]+)', makefile, re.M)
    if not match or set(match[1].split('#', 1)[0].split()) != set(data['source_files']):
        raise ValueError('Keep PROJECT_SOURCES in test/Makefile in sync with info.yaml source_files.')
    return top, sources


def tool(name):
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f'{name} is not on PATH. Run through tt.cmd on Windows.')
    return path


def doctor():
    import cocotb

    top, sources = project()
    print(f'Project: {top} ({len(sources)} source files)', flush=True)
    print(f'Python: {sys.version.split()[0]} at {sys.executable}', flush=True)
    print(f'cocotb: {cocotb.__version__}', flush=True)
    for name in ('iverilog', 'vvp', 'yosys', 'gtkwave'):
        print(f'{name}: {tool(name)}', flush=True)
    suite = os.environ.get('YOSYSHQ_ROOT')
    if suite:
        ivl = Path(suite) / 'lib' / 'ivl'
        if not (ivl / 'ivl.exe').is_file():
            raise RuntimeError(f'Icarus backend is missing from {ivl}')
        version = Path(suite) / 'VERSION'
        print(f'OSS CAD Suite: {version.read_text().strip()}', flush=True)
    print('Source list matches the GitHub Actions Makefile.', flush=True)


def simulate(gates=False):
    from cocotb_tools.check_results import get_results
    from cocotb_tools.runner import get_runner

    _, sources = project()
    defines = {}
    if gates:
        pdk_root = os.environ.get('PDK_ROOT')
        if not pdk_root:
            raise RuntimeError('gl-test needs PDK_ROOT and test/gate_level_netlist.v. See docs/windows-and-github.md.')
        models = Path(pdk_root) / 'sky130A' / 'libs.ref' / 'sky130_fd_sc_hd' / 'verilog'
        sources = [models / 'primitives.v', models / 'sky130_fd_sc_hd.v', TEST / 'gate_level_netlist.v']
        for source in sources:
            if not source.is_file():
                raise RuntimeError(f'Gate-level dependency missing: {source}')
        defines = dict(GL_TEST=1, FUNCTIONAL=1, USE_POWER_PINS=1, SIM=1, UNIT_DELAY='#1')
    sources.append(TEST / 'tb.v')
    build_args = []
    test_args = []
    if os.name == 'nt' and os.environ.get('YOSYSHQ_ROOT'):
        # This Windows release has a build-machine /yosyshq path compiled in.
        build_args = ['-B', str(Path(os.environ['YOSYSHQ_ROOT']) / 'lib' / 'ivl')]
        # Avoid vvp's GetShortPathName-based default module discovery. All VPI
        # modules already have absolute paths from -B and cocotb's configuration.
        test_args = ['-M', '-']
    sys.path.insert(0, str(TEST))
    runner = get_runner('icarus')
    runner.build(
        sources=sources, hdl_toplevel='tb', includes=[ROOT / 'src'],
        defines=defines, build_args=build_args,
        build_dir=TEST / 'sim_build' / 'native' / ('gl' if gates else 'rtl'),
        always=True,
    )
    results = runner.test(
        hdl_toplevel='tb', test_module='test', test_dir=TEST,
        results_xml=TEST / 'results.xml', test_args=test_args, waves=True,
    )
    tests, failures = get_results(results)
    if tests < 1 or failures:
        raise RuntimeError(f'Simulation failed: {failures} failures in {tests} tests. See {results}')
    print(f'PASS: {tests} cocotb test(s); waveform: {TEST / "tb.fst"}', flush=True)


def synthesize():
    top, sources = project()
    output = ROOT / 'build' / 'synth'
    output.mkdir(parents=True, exist_ok=True)

    def quoted(path):
        return '"' + Path(path).as_posix().replace('"', '\\"') + '"'

    commands = [f'read_verilog -I{quoted(ROOT / "src")} ' + ' '.join(map(quoted, sources)),
                f'hierarchy -check -top {top}', f'synth -top {top}', 'check -assert', 'stat',
                f'write_verilog -noattr {quoted(output / "netlist.v")}',
                f'write_json {quoted(output / "netlist.json")}']
    script = output / 'synth.ys'
    script.write_text('\n'.join(commands) + '\n', encoding='utf-8')
    subprocess.run([tool('yosys'), '-q', '-l', str(output / 'yosys.log'), '-s', str(script)], cwd=ROOT, check=True)
    print(f'Synthesis passed. Reports and generic netlist: {output}', flush=True)
    print('The Sky130 GDS and physical checks run in the GitHub gds workflow.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['doctor', 'test', 'gl-test', 'synth'])
    args = parser.parse_args()
    if args.command == 'doctor':
        doctor()
    elif args.command == 'synth':
        synthesize()
    else:
        simulate(gates=args.command == 'gl-test')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
