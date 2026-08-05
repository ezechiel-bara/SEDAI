import 'dart:async';
import 'package:flutter/material.dart';
import 'package:syncfusion_flutter_gauges/gauges.dart';
import '../core/constants.dart';
import '../models/vehicle_data.dart';
import '../services/websocket_service.dart';
import '../widgets/automotive_gauge.dart';
import 'analysis_screen.dart';
import 'chat_screen.dart';

class DashboardScreen extends StatefulWidget {
  final WebSocketService wsService;

  const DashboardScreen({super.key, required this.wsService});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  VehicleData _data = VehicleData.initial();
  final bool _voiceActive = false;
  bool _analysisOpen = false; // Garde contre les doubles ouvertures d'analyse

  StreamSubscription? _dataSub;
  StreamSubscription? _diagnosisSub;

  @override
  void initState() {
    super.initState();

    _dataSub = widget.wsService.dataStream.listen((data) {
      if (mounted) setState(() => _data = data);
    });

    _diagnosisSub = widget.wsService.diagnosisStream.listen((result) {
      if (mounted && !_analysisOpen) {
        _analysisOpen = true;
        Navigator.push(
          context,
          MaterialPageRoute(
            settings: const RouteSettings(name: 'analysis'),
            builder: (_) => AnalysisScreen(result: result),
          ),
        ).then((_) => _analysisOpen = false); // Réinitialise quand l'écran se ferme
      }
    });
  }

  @override
  void dispose() {
    _dataSub?.cancel();
    _diagnosisSub?.cancel();
    super.dispose();
  }

  // ── Bouton Push-to-Talk ───────────────────────────────────────────────────
  void _onMicPressed() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => ChatScreen(
          wsService: widget.wsService,
          autoStartVoice: true,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.of(context).size.width;
    final crossAxisCount = width > 1100 ? 4 : (width > 700 ? 3 : 2);
    final isConnected = _data.statutObd.toLowerCase().contains('connecté') &&
        !_data.statutObd.toLowerCase().contains('déconnecté');

    return Column(
      children: [
        // ── Statut OBD ────────────────────────────────────────────────────
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(vertical: 6),
          color: isConnected
              ? AppColors.successGreen.withValues(alpha: 0.15)
              : AppColors.alertOrange.withValues(alpha: 0.1),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                isConnected ? Icons.cable : Icons.power_off,
                size: 14,
                color:
                    isConnected ? AppColors.accentGreen : AppColors.alertOrange,
              ),
              const SizedBox(width: 8),
              Text(
                'STATUT OBD : ${_data.statutObd.toUpperCase()}',
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 2.0,
                  color: isConnected
                      ? AppColors.accentGreen
                      : AppColors.alertOrange,
                ),
              ),
            ],
          ),
        ),

        // ── Grille des jauges ─────────────────────────────────────────────
        Expanded(
          child: GridView.count(
            padding: const EdgeInsets.fromLTRB(14, 14, 14, 6),
            crossAxisCount: crossAxisCount,
            mainAxisSpacing: 12,
            crossAxisSpacing: 12,
            children: [
              AutomotiveGauge(
                title: 'Vitesse',
                unit: 'km/h',
                value: _data.vitesse,
                min: 0,
                max: 220,
                accentColor: AppColors.accentCyan,
                isWarning: isConnected && _data.vitesse >= 180,
                ranges: [
                  GaugeRange(
                    startValue: 180,
                    endValue: 220,
                    color: AppColors.dangerRed.withValues(alpha: 0.25),
                  ),
                ],
              ),
              AutomotiveGauge(
                title: 'Régime moteur',
                unit: 'RPM',
                value: _data.regime,
                min: 0,
                max: 8000,
                accentColor: AppColors.accentCyan,
                isWarning: isConnected && _data.regime >= 6500,
                ranges: [
                  GaugeRange(
                    startValue: 6500,
                    endValue: 8000,
                    color: AppColors.dangerRed.withValues(alpha: 0.25),
                  ),
                ],
              ),
              AutomotiveGauge(
                title: 'Temp. Moteur',
                unit: '°C',
                value: _data.tempMoteur,
                min: 0,
                max: 130,
                accentColor: AppColors.alertOrange,
                isWarning: isConnected && _data.tempMoteur >= 100, // Surchauffe
                ranges: [
                  GaugeRange(
                    startValue: 100,
                    endValue: 130,
                    color: AppColors.alertOrange.withValues(alpha: 0.25),
                  ),
                ],
              ),
              AutomotiveGauge(
                title: 'Débit air (MAF)',
                unit: 'g/s',
                value: _data.maf,
                min: 0,
                max: 40,
                accentColor: AppColors.accentGreen,
              ),
              AutomotiveGauge(
                title: 'Lambda (O₂)',
                unit: 'λ',
                value: _data.lambda,
                min: 0,
                max: 1.5,
                accentColor: AppColors.accentGreen,
                isWarning: isConnected &&
                    (_data.lambda < 0.8 ||
                        _data.lambda > 1.2), // Mélange très pauvre/très riche
                ranges: [
                  GaugeRange(
                    startValue: 0,
                    endValue: 0.9,
                    color: AppColors.alertOrange.withValues(alpha: 0.2),
                  ),
                  GaugeRange(
                    startValue: 1.1,
                    endValue: 1.5,
                    color: AppColors.alertOrange.withValues(alpha: 0.2),
                  ),
                ],
              ),
              AutomotiveGauge(
                title: 'Batterie',
                unit: 'V',
                value: _data.batterie,
                min: 10,
                max: 15,
                accentColor: AppColors.accentBlue,
                isWarning:
                    isConnected && _data.batterie < 11.5, // Tension trop basse
                ranges: [
                  GaugeRange(
                    startValue: 10,
                    endValue: 11.5,
                    color: AppColors.dangerRed.withValues(alpha: 0.25),
                  ),
                ],
              ),
              AutomotiveGauge(
                title: 'Pression MAP',
                unit: 'kPa',
                value: _data.pressionMap,
                min: 0,
                max: 255,
                accentColor: AppColors.accentCyan,
                isWarning: isConnected &&
                    _data.pressionMap >= 200, // Surpression admission
                ranges: [
                  GaugeRange(
                    startValue: 200,
                    endValue: 255,
                    color: AppColors.alertOrange.withValues(alpha: 0.25),
                  ),
                ],
              ),
              AutomotiveGauge(
                title: 'Pression Huile',
                unit: 'kPa',
                value: _data.pressionHuile,
                min: 0,
                max: 600,
                accentColor: AppColors.alertOrange,
                isWarning: isConnected &&
                    _data.pressionHuile > 0 &&
                    (_data.pressionHuile < 50 ||
                        _data.pressionHuile >=
                            450), // Si pression disponible, vérifie plages anormales
                ranges: [
                  GaugeRange(
                    startValue: 0,
                    endValue: 50,
                    color: AppColors.dangerRed.withValues(alpha: 0.25),
                  ),
                  GaugeRange(
                    startValue: 450,
                    endValue: 600,
                    color: AppColors.alertOrange.withValues(alpha: 0.25),
                  ),
                ],
              ),
              AutomotiveGauge(
                title: 'Niveau Carburant',
                unit: '%',
                value: _data.niveauCarburant,
                min: 0,
                max: 100,
                accentColor: AppColors.alertOrange,
                isWarning: isConnected && _data.niveauCarburant <= 10,
                ranges: [
                  GaugeRange(
                    startValue: 0,
                    endValue: 10,
                    color: AppColors.dangerRed.withValues(alpha: 0.25),
                  ),
                ],
              ),
            ],
          ),
        ),

        // ── Barre d'actions ───────────────────────────────────────────────
        Container(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 20),
          decoration: const BoxDecoration(
            color: AppColors.surface,
            border: Border(
              top: BorderSide(color: AppColors.cardBorder, width: 1),
            ),
          ),
          child: Row(
            children: [
              // Bouton diagnostic IA
              Expanded(
                child: SizedBox(
                  height: 52,
                  child: ElevatedButton.icon(
                    onPressed: widget.wsService.requestDiagnostic,
                    icon: const Icon(Icons.auto_awesome_outlined, size: 18),
                    label: const Text('DIAGNOSTIC IA'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.accentCyan,
                      foregroundColor: AppColors.background,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),

              // Bouton microphone PTT
              _MicButton(
                active: _voiceActive,
                onTap: _onMicPressed,
              ),
            ],
          ),
        ),
      ],
    );
  }
}

// ── Widget bouton microphone ──────────────────────────────────────────────────
class _MicButton extends StatelessWidget {
  final bool active;
  final VoidCallback onTap;

  const _MicButton({required this.active, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final color = active ? AppColors.dangerRed : AppColors.accentCyan;

    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        width: 52,
        height: 52,
        decoration: BoxDecoration(
          color: color.withValues(alpha: active ? 0.15 : 0.08),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: color.withValues(alpha: active ? 0.8 : 0.4),
            width: 1.5,
          ),
          boxShadow: active
              ? [
                  BoxShadow(
                    color: AppColors.dangerRed.withValues(alpha: 0.3),
                    blurRadius: 12,
                    spreadRadius: 2,
                  ),
                ]
              : [],
        ),
        child: Icon(
          active ? Icons.mic : Icons.mic_none_outlined,
          color: color,
          size: 22,
        ),
      ),
    );
  }
}
