"""
Phase 3A opposite-drive ERT reconstruction tool.

Uses opposite current injection pairs and adjacent voltage measurements.
Requires matching firmware output order.
"""

from __future__ import annotations

import phase3a_reconstruct as base


def main() -> None:
    args = base.parse_args()
    frame_numbers = base.capture_frame_numbers(args.frames)
    protocol = base.build_opposite_protocol(base.N_ELECTRODES)
    eit_mesh, solver = base.create_solver(protocol)
    logger = base.create_frame_logger(args, "opposite")
    run_id = base.datetime.now().strftime("%Y%m%d-%H%M%S")
    fig = None
    delta_rms_values: list[float] = []

    print(f"[Serial] Connecting to {args.port} at {args.baud} baud...")
    ser = base.serial.Serial(args.port, args.baud, timeout=0.5)
    base.time.sleep(args.baseline_wait)
    ser.reset_input_buffer()

    try:
        print("[Capture] Requesting opposite-drive baseline frame...")
        ser.write(b"s\n")
        baseline_records = base.read_one_frame(ser)
        baseline = base.records_to_vector(baseline_records, protocol)
        if logger is not None:
            logger.write_frame(run_id, 0, baseline_records)
            print(f"[Log] writing up to {logger.max_frames} frames to {logger.path}")
            if logger.max_frames < args.frames + 1:
                print(
                    f"[Log warning] {args.frames + 1} frames include the baseline, "
                    f"but the log limit is {logger.max_frames}."
                )
        print(f"[Baseline] captured {len(baseline)} measurements")

        fig, ax = base.create_reconstruction_plot()
        print(f"[Run] Capturing {args.frames} opposite-drive frames. Press Ctrl+C to stop early.")
        for frame_index in frame_numbers:
            ser.write(b"s\n")
            current_records = base.read_one_frame(ser)
            current = base.records_to_vector(current_records, protocol)
            if logger is not None:
                logger.write_frame(run_id, frame_index, current_records)
            ds = base.reconstruct_difference(baseline, current, solver)
            delta_rms = float(base.np.sqrt(base.np.mean((current - baseline) ** 2)))
            delta_rms_values.append(delta_rms)
            print(
                f"[Frame {frame_index}/{args.frames}] "
                f"min={current.min():+.3f}mV max={current.max():+.3f}mV "
                f"delta_rms={delta_rms:.3f}mV"
            )
            base.update_reconstruction_plot(
                fig,
                ax,
                eit_mesh,
                ds,
                "Phase 3A Opposite-Drive ERT Reconstruction",
            )
        base.print_stability_summary(delta_rms_values)
        print("[Complete] Capture finished. Close the plot window to exit.")
    except KeyboardInterrupt:
        print("\nStopped.")
        base.print_stability_summary(delta_rms_values)
    finally:
        if logger is not None:
            logger.close()
            print(f"[Log] saved {logger.frames_written} frames to {logger.path}")
        ser.close()
    if fig is not None:
        base.plt.ioff()
        base.plt.show()


if __name__ == "__main__":
    main()
