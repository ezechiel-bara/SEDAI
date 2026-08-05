import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:intl/intl.dart';
import '../core/constants.dart';
import '../models/vehicle_data.dart';
import '../models/diagnosis_record.dart';
import '../services/storage_service.dart';

class AnalysisScreen extends StatefulWidget {
  final DiagnosisResult result;

  const AnalysisScreen({super.key, required this.result});

  @override
  State<AnalysisScreen> createState() => _AnalysisScreenState();
}

class _AnalysisScreenState extends State<AnalysisScreen> {
  bool _saved = false;
  bool _timerPaused = false;

  // Durée avant retour automatique (2 minutes)
  static const int _totalSeconds = 120;
  int _secondsLeft = _totalSeconds;
  Timer? _countdownTimer;

  @override
  void initState() {
    super.initState();
    // Sauvegarde automatique dès l'arrivée du rapport
    _autoSave();
    // Démarrage du compte à rebours
    _startCountdown();
  }

  @override
  void dispose() {
    _countdownTimer?.cancel();
    super.dispose();
  }

  // ── Sauvegarde automatique ────────────────────────────────────────────────
  Future<void> _autoSave() async {
    final record = DiagnosisRecord(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      content: widget.result.content,
      vehicleMarque: StorageService.getVehicleMarque(),
      vehicleModele: StorageService.getVehicleModele(),
      vehicleMoteur: StorageService.getVehicleMoteur(),
      timestamp: widget.result.timestamp,
    );
    await StorageService.addRecord(record);
    if (mounted) setState(() => _saved = true);
  }

  // ── Compte à rebours ──────────────────────────────────────────────────────
  void _startCountdown() {
    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_timerPaused) return;
      if (!mounted) {
        timer.cancel();
        return;
      }
      setState(() {
        if (_secondsLeft <= 1) {
          timer.cancel();
          Navigator.of(context).pop();
        } else {
          _secondsLeft--;
        }
      });
    });
  }

  void _pauseResumeTimer() {
    setState(() => _timerPaused = !_timerPaused);
  }

  void _returnNow() {
    _countdownTimer?.cancel();
    Navigator.of(context).pop();
  }

  String get _timerLabel {
    final m = (_secondsLeft ~/ 60).toString().padLeft(2, '0');
    final s = (_secondsLeft % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  double get _timerProgress => _secondsLeft / _totalSeconds;

  // ── Véhicule ──────────────────────────────────────────────────────────────
  String get _vehicleLabel {
    final parts = [
      StorageService.getVehicleMarque(),
      StorageService.getVehicleModele(),
      StorageService.getVehicleMoteur(),
    ].where((s) => s.isNotEmpty).toList();
    return parts.isEmpty ? 'Véhicule non renseigné' : parts.join(' · ');
  }

  // ── Sauvegarde manuelle ───────────────────────────────────────────────────
  Future<void> _saveToHistory() async {
    if (_saved) return;
    await _autoSave();
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Row(
            children: [
              Icon(Icons.check_circle_outline,
                  color: AppColors.accentGreen, size: 18),
              SizedBox(width: 10),
              Text('Diagnostic sauvegardé dans l\'historique.',
                  style: TextStyle(color: AppColors.textPrimary)),
            ],
          ),
          backgroundColor: AppColors.surface,
          behavior: SnackBarBehavior.floating,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final dateStr =
        DateFormat('dd/MM/yyyy  HH:mm').format(widget.result.timestamp);

    return Scaffold(
      appBar: AppBar(
        title: const Text('ANALYSE IA'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded,
              color: AppColors.accentCyan, size: 18),
          onPressed: _returnNow,
        ),
        actions: [
          if (_saved)
            const Padding(
              padding: EdgeInsets.only(right: 16),
              child: Icon(Icons.bookmark_added, color: AppColors.accentGreen),
            )
          else
            IconButton(
              icon: const Icon(Icons.bookmark_add_outlined,
                  color: AppColors.accentCyan),
              tooltip: 'Sauvegarder',
              onPressed: _saveToHistory,
            ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Badge diagnostic terminé ──────────────────────────────────
            Center(
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                decoration: BoxDecoration(
                  color: AppColors.accentGreen.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(30),
                  border: Border.all(
                    color: AppColors.accentGreen.withValues(alpha: 0.5),
                    width: 1.5,
                  ),
                ),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.check_circle_outline,
                        color: AppColors.accentGreen, size: 18),
                    SizedBox(width: 10),
                    Text(
                      'DIAGNOSTIC TERMINÉ',
                      style: TextStyle(
                        color: AppColors.accentGreen,
                        fontWeight: FontWeight.w700,
                        fontSize: 14,
                        letterSpacing: 1.5,
                      ),
                    ),
                  ],
                ),
              ).animate().fadeIn().scale(begin: const Offset(0.9, 0.9)),
            ),

            const SizedBox(height: 16),

            // ── Compte à rebours ──────────────────────────────────────────
            _AutoReturnBanner(
              timerLabel: _timerLabel,
              progress: _timerProgress,
              paused: _timerPaused,
              onPauseResume: _pauseResumeTimer,
              onReturnNow: _returnNow,
            ).animate().fadeIn(delay: 100.ms),

            const SizedBox(height: 20),

            // ── Informations contextuelles ────────────────────────────────
            Row(
              children: [
                Expanded(
                  child: _infoTile(
                    icon: Icons.directions_car_outlined,
                    label: 'VÉHICULE',
                    value: _vehicleLabel,
                  ),
                ),
                const SizedBox(width: 12),
                _infoTile(
                  icon: Icons.access_time_outlined,
                  label: 'DATE',
                  value: dateStr,
                ),
              ],
            ).animate().fadeIn(delay: 150.ms),

            const SizedBox(height: 20),

            // ── En-tête rapport ───────────────────────────────────────────
            Row(
              children: [
                Container(
                  width: 3,
                  height: 16,
                  margin: const EdgeInsets.only(right: 10),
                  decoration: BoxDecoration(
                    color: AppColors.accentCyan,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const Text(
                  'RAPPORT IA LOCALE (PHI-3 MINI / GEMMA3 4B)',
                  style: TextStyle(
                    color: AppColors.textSecondary,
                    fontWeight: FontWeight.w700,
                    fontSize: 10,
                    letterSpacing: 1.8,
                  ),
                ),
              ],
            ),

            const SizedBox(height: 10),

            // ── Contenu du rapport ────────────────────────────────────────
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: AppColors.cardBorder),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.25),
                    blurRadius: 20,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: SelectableText(
                widget.result.content.isNotEmpty
                    ? widget.result.content
                    : 'Aucun diagnostic reçu.',
                style: const TextStyle(
                  fontSize: 15,
                  height: 1.7,
                  color: AppColors.textPrimary,
                  letterSpacing: 0.3,
                ),
              ),
            )
                .animate()
                .slideY(begin: 0.08, curve: Curves.easeOut, delay: 200.ms),

            const SizedBox(height: 24),

            // ── Bouton retour manuel ──────────────────────────────────────
            SizedBox(
              width: double.infinity,
              height: 50,
              child: ElevatedButton.icon(
                onPressed: _returnNow,
                icon: const Icon(Icons.dashboard_outlined, size: 18),
                label: const Text('RETOUR AU DASHBOARD'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.surfaceAlt,
                  foregroundColor: AppColors.textSecondary,
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10)),
                ),
              ),
            ),

            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  Widget _infoTile({
    required IconData icon,
    required String label,
    required String value,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.cardBorder),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: AppColors.textSecondary, size: 14),
          const SizedBox(width: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label,
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 9,
                    letterSpacing: 1.5,
                  )),
              const SizedBox(height: 2),
              Text(value,
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  )),
            ],
          ),
        ],
      ),
    );
  }
}

// ── Widget bannière de compte à rebours ──────────────────────────────────────
class _AutoReturnBanner extends StatelessWidget {
  final String timerLabel;
  final double progress;
  final bool paused;
  final VoidCallback onPauseResume;
  final VoidCallback onReturnNow;

  const _AutoReturnBanner({
    required this.timerLabel,
    required this.progress,
    required this.paused,
    required this.onPauseResume,
    required this.onReturnNow,
  });

  @override
  Widget build(BuildContext context) {
    final isUrgent = progress < 0.2; // rouge dans les 24 dernières secondes
    final color = isUrgent
        ? AppColors.dangerRed
        : (paused ? AppColors.alertOrange : AppColors.accentCyan);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Column(
        children: [
          // Ligne info + boutons
          Row(
            children: [
              Icon(
                paused ? Icons.pause_circle_outline : Icons.timer_outlined,
                color: color,
                size: 16,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  paused
                      ? 'Retour automatique suspendu'
                      : 'Retour automatique dans',
                  style: TextStyle(
                    color: color,
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 0.5,
                  ),
                ),
              ),
              // Compte à rebours
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  timerLabel,
                  style: TextStyle(
                    color: color,
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
              ),
              const SizedBox(width: 8),
              // Pause / Reprendre
              GestureDetector(
                onTap: onPauseResume,
                child: Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                   color: color.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Icon(
                    paused ? Icons.play_arrow_rounded : Icons.pause_rounded,
                    color: color,
                    size: 16,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          // Barre de progression
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: progress,
              minHeight: 3,
              backgroundColor: color.withValues(alpha: 0.1),
              valueColor: AlwaysStoppedAnimation<Color>(color),
            ),
          ),
        ],
      ),
    );
  }
}
