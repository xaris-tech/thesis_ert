# Bring-Up and Testing

## Stage 1: Power

- Verify 12 V adapter polarity and voltage.
- Verify converter `+9 V`, center ground, and `-9 V`.
- Verify 3.3 V module supply.
- Run unloaded for ten minutes and check temperature and drift.

Pass: correct polarity, stable rails, no overheating.

## Stage 2: Howland Source

- Keep all muxes disconnected.
- Test the lowest current range first.
- Use 470 ohm, 1 kohm, 2.2 kohm, 4.7 kohm, and 10 kohm loads.
- Calculate current from both load and shunt voltage.
- Check five-minute drift and OPA output headroom.

Pass: approximately constant current, within about 5% over the declared load
range, with no saturation or heating.

## Stage 3: Current Monitor and ADC

- Compare ADS1115 shunt and differential readings with the multimeter.
- Test every ADC gain used by firmware.
- Confirm A0-A3 never leave the 0-3.3 V supply range.

Pass: correct polarity and repeatable readings within the documented error.

## Stage 4: Mux Matrix

- Disconnect current and electrodes.
- Verify all 48 C0-C11 paths with continuity/resistance checks.
- Verify all muxes isolate when disabled.
- Confirm address and label mapping.

Pass: no swapped, shorted, missing, or duplicate electrode paths.

## Stage 5: Integrated Dummy Network

- Run complete adjacent and opposite frames.
- Confirm forward/reverse mapping.
- Confirm safe idle during every switch.
- Confirm expected record counts and no parser errors.

## Stage 6: Saline Tank

- Capture warm-up and stationary scans.
- Establish drift/noise floor.
- Add insulating then conductive targets at known sectors.
- Repeat after removing and reinstalling the target.

Pass: anomaly response exceeds baseline variation and localizes repeatedly in
the correct sector.

## Stage 7: Tree Samples

- Start with banana pseudostem, then cut trunk.
- Scan intact baseline without moving electrodes afterward.
- Create and document a controlled anomaly.
- Repeat matching scans and compare against ground truth.

