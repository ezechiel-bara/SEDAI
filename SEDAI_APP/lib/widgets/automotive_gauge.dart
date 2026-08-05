import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:syncfusion_flutter_gauges/gauges.dart';
import '../core/constants.dart';

class AutomotiveGauge extends StatelessWidget {
  final String title;
  final String unit;
  final double value;
  final double min;
  final double max;
  final List<GaugeRange>? ranges;
  final Color accentColor;
  final bool isWarning;

  const AutomotiveGauge({
    super.key,
    required this.title,
    required this.unit,
    required this.value,
    required this.min,
    required this.max,
    this.ranges,
    this.accentColor = AppColors.accentCyan,
    this.isWarning = false,
  });

  @override
  Widget build(BuildContext context) {
    // Si la valeur dépasse la tolérance, la jauge clignotera doucement en rouge
    Widget gaugeContainer = Container(
      padding: const EdgeInsets.fromLTRB(10, 10, 10, 8),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.cardBorder, width: 1),
        boxShadow: [
          BoxShadow(
            color: (isWarning ? AppColors.dangerRed : accentColor).withValues(alpha: isWarning ? 0.2 : 0.04),
            blurRadius: isWarning ? 20 : 16,
            spreadRadius: isWarning ? 4 : 2,
          ),
        ],
      ),
      child: Column(
        children: [
          Expanded(
            child: SfRadialGauge(
              axes: <RadialAxis>[
                RadialAxis(
                  minimum: min,
                  maximum: max,
                  startAngle: 145,
                  endAngle: 35,
                  showLabels: true,
                  showTicks: true,
                  axisLineStyle: const AxisLineStyle(
                    thickness: 0.08,
                    thicknessUnit: GaugeSizeUnit.factor,
                    color: AppColors.cardBorder,
                  ),
                  axisLabelStyle: const GaugeTextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 9,
                    fontWeight: FontWeight.w500,
                  ),
                  majorTickStyle: const MajorTickStyle(
                    length: 0.08,
                    thickness: 1.5,
                    color: AppColors.textSecondary,
                    lengthUnit: GaugeSizeUnit.factor,
                  ),
                  minorTickStyle: const MinorTickStyle(
                    length: 0.04,
                    thickness: 1,
                    color: AppColors.textMuted,
                    lengthUnit: GaugeSizeUnit.factor,
                  ),
                  ranges: ranges,
                  pointers: <GaugePointer>[
                    RangePointer(
                      value: value,
                      width: 0.08,
                      sizeUnit: GaugeSizeUnit.factor,
                      color: accentColor.withValues(alpha: 0.25),
                      enableAnimation: true,
                      animationType: AnimationType.easeOutBack,
                    ),
                    NeedlePointer(
                      value: value,
                      needleLength: 0.75,
                      enableAnimation: true,
                      animationType: AnimationType.easeOutBack,
                      animationDuration: 800,
                      needleStartWidth: 1,
                      needleEndWidth: 3.5,
                      needleColor: accentColor,
                      knobStyle: KnobStyle(
                        knobRadius: 0.07,
                        sizeUnit: GaugeSizeUnit.factor,
                        color: accentColor,
                      ),
                    ),
                  ],
                  annotations: <GaugeAnnotation>[
                    GaugeAnnotation(
                      widget: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            _formatValue(value),
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.w700,
                              color: accentColor,
                              height: 1.0,
                            ),
                          ),
                          Text(
                            unit,
                            style: const TextStyle(
                              fontSize: 9,
                              color: AppColors.textSecondary,
                              letterSpacing: 0.5,
                            ),
                          ),
                        ],
                      ),
                      angle: 90,
                      positionFactor: 0.52,
                    ),
                  ],
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text(
              title.toUpperCase(),
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w700,
                letterSpacing: 1.5,
                color: isWarning ? AppColors.dangerRed : AppColors.textSecondary,
              ),
            ),
          ),
        ],
      ),
    );

    // Retour d'animation visuel sans effet sonore ou haptique
    if (isWarning) {
      return gaugeContainer.animate(onPlay: (controller) => controller.repeat(reverse: true))
          .tint(color: AppColors.dangerRed.withValues(alpha: 0.4), duration: 800.ms, delay: 100.ms)
          .scale(end: const Offset(1.02, 1.02), duration: 800.ms);
    }
    
    return gaugeContainer;
  }

  String _formatValue(double v) {
    if (v >= 1000) return v.toStringAsFixed(0);
    if (v >= 10) return v.toStringAsFixed(0);
    return v.toStringAsFixed(1);
  }
}
