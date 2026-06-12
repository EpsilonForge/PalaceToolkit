# Examples

Complete worked examples covering the full workflow: geometry, meshing,
Palace configuration, simulation, and post-processing.

---

## Antennas

<div class="ptk-gallery-grid">
	<a class="ptk-gallery-link" href="horn_antenna.html">
		<article class="ptk-gallery-card">
			<img src="../_static/horn.png" alt="Horn Antenna preview">
			<h3>Horn Antenna</h3>
			<p>WR-90 rectangular waveguide transition to a horn antenna with waveport boundaries.</p>
		</article>
	</a>
	<a class="ptk-gallery-link" href="dipole_antenna_mesh.html">
		<article class="ptk-gallery-card">
			<img src="../_static/dipole.png" alt="Dipole Antenna Mesh preview">
			<h3>Dipole Antenna</h3>
			<p>Half-wave dipole geometry and mesh generation workflow.</p>
		</article>
	</a>
	<a class="ptk-gallery-link" href="monopole_antenna.html">
		<article class="ptk-gallery-card">
			<img src="../_static/dipole.png" alt="Monopole Antenna preview">
			<h3>Monopole Antenna</h3>
			<p>Quarter-wave monopole example with meshing and Palace setup.</p>
		</article>
	</a>
	<a class="ptk-gallery-link" href="patch_antenna.html">
		<article class="ptk-gallery-card">
			<img src="../_static/patch.png" alt="Patch Antenna preview">
			<h3>Patch Antenna</h3>
			<p>Rectangular patch antenna model with substrate, feed, and boundary setup.</p>
		</article>
	</a>
	<a class="ptk-gallery-link" href="vivaldi_antenna.html">
		<article class="ptk-gallery-card">
			<img src="../_static/vivaldi.png" alt="Vivaldi Antenna preview">
			<h3>Vivaldi Antenna</h3>
			<p>Tapered-slot (Vivaldi) antenna geometry and simulation example.</p>
		</article>
	</a>
</div>

## Planar Microwave Circuits

<div class="ptk-gallery-grid">
	<a class="ptk-gallery-link" href="open_ended_stub.html">
		<article class="ptk-gallery-card">
			<img src="../_static/open_ended.png" alt="Open-ended Stub preview">
			<h3>Open-ended Stub</h3>
			<p>Open-ended microstrip stub component with geometry and simulation setup.</p>
		</article>
	</a>
	<a class="ptk-gallery-link" href="l_antenna.html">
		<article class="ptk-gallery-card">
			<img src="../_static/bend.png" alt="L Antenna preview">
			<h3>L Antenna</h3>
			<p>Bent-wire L-shaped antenna workflow including geometry and driven simulation setup.</p>
		</article>
	</a>	
	<a class="ptk-gallery-link" href="step_in_width.html">
		<article class="ptk-gallery-card">
			<img src="../_static/step.png" alt="Step in Width preview">
			<h3>Step in Width</h3>
			<p>Microstrip step-discontinuity example for meshing and EM analysis.</p>
		</article>
	</a>
</div>

## Waveguide Structures

<div class="ptk-gallery-grid">
	<a class="ptk-gallery-link" href="waveguide_box.html">
		<article class="ptk-gallery-card">
			<img src="../_static/box.png" alt="Waveguide Box preview">
			<h3>Waveguide Box</h3>
			<p>Closed waveguide cavity/box example including full 3D setup and analysis.</p>
		</article>
	</a>
	<a class="ptk-gallery-link" href="coax.html">
		<article class="ptk-gallery-card">
			<img src="../_static/coax.png" alt="Coax preview">
			<h3>Coax</h3>
			<p>Coaxial line baseline example for geometry, mesh, and configuration setup.</p>
		</article>
	</a>
	<a class="ptk-gallery-link" href="coax_to_waveguide.html">
		<article class="ptk-gallery-card">
			<img src="../_static/coax_to_waveguide.png" alt="Coax to Waveguide Transition preview">
			<h3>Coax to Waveguide Transition</h3>
			<p>Driven coax-to-waveguide transition example including geometry, mesh, and setup.</p>
		</article>
	</a>	
</div>

## Waveguide Mode Solver

<div class="ptk-gallery-grid">
	<a class="ptk-gallery-link" href="hollow_waveguide_modes.html">
		<article class="ptk-gallery-card">
			<img src="../_static/hollow_waveguide.png" alt="Hollow Rectangular Waveguide Modes preview">
			<h3>Hollow Rectangular Waveguide Modes</h3>
			<p>PEC waveguide eigenmodes compared with analytic TE/TM propagation constants.</p>
		</article>
	</a>
	<a class="ptk-gallery-link" href="dielectric_waveguide_modes.html">
		<article class="ptk-gallery-card">
			<img src="../_static/dielectric_waveguide.png" alt="Dielectric Waveguide Modes preview">
			<h3>Dielectric Waveguide Modes</h3>
			<p>Rectangular dielectric core in cladding with guided-mode classification and field plots.</p>
		</article>
	</a>
	<a class="ptk-gallery-link" href="microstrip_modes.html">
		<article class="ptk-gallery-card">
			<img src="../_static/microstrip.png" alt="Microstrip Modes preview">
			<h3>Microstrip Modes</h3>
			<p>Boxed 2D microstrip cross-section with PEC strip and outer conductor boundaries for hybrid mode analysis.</p>
		</article>
	</a>
	<a class="ptk-gallery-link" href="slotline_modes.html">
		<article class="ptk-gallery-card">
			<img src="../_static/slotline.png" alt="Slotline Modes preview">
			<h3>Slotline Modes</h3>
			<p>Boxed 2D slotline cross-section with two PEC slot conductors and open outer boundaries.</p>
		</article>
	</a>
	<a class="ptk-gallery-link" href="differential_microstrip_modes.html">
		<article class="ptk-gallery-card">
			<img src="../_static/differential.png" alt="Differential Microstrip Modes preview">
			<h3>Differential Microstrip Modes</h3>
			<p>Boxed 2D differential microstrip with ground plane and two PEC strips for coupled-mode analysis.</p>
		</article>
	</a>
</div>

```{toctree}
:caption: Antennas
:maxdepth: 1
:hidden:

horn_antenna
dipole_antenna_mesh
monopole_antenna
l_antenna
patch_antenna
vivaldi_antenna
```

```{toctree}
:caption: Planar Microwave Circuits
:maxdepth: 1
:hidden:

coax
coax_to_waveguide
open_ended_stub
step_in_width
```

```{toctree}
:caption: Waveguide Structures
:maxdepth: 1
:hidden:

waveguide_box
```

```{toctree}
:caption: Waveguide Mode Solver
:maxdepth: 1
:hidden:

hollow_waveguide_modes
dielectric_waveguide_modes
microstrip_modes
slotline_modes
differential_microstrip_modes
```
