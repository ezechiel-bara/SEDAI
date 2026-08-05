import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../core/constants.dart';
import '../services/storage_service.dart';
import 'main_screen.dart';

class SetupScreen extends StatefulWidget {
  const SetupScreen({super.key});

  @override
  State<SetupScreen> createState() => _SetupScreenState();
}

class _SetupScreenState extends State<SetupScreen> {
  final _formKey = GlobalKey<FormState>();
  final _ipCtrl = TextEditingController(text: AppConstants.defaultIp);
  final _portCtrl = TextEditingController(text: AppConstants.defaultPort);
  final _marqueCtrl = TextEditingController();
  final _modeleCtrl = TextEditingController();
  final _modMoteurCtrl = TextEditingController();
  final _typeMoteurCtrl = TextEditingController();
  final _anneeCtrl = TextEditingController();
  final _transmissionCtrl = TextEditingController(text: 'Automatique');

  bool _saving = false;

  @override
  void dispose() {
    _ipCtrl.dispose();
    _portCtrl.dispose();
    _marqueCtrl.dispose();
    _modeleCtrl.dispose();
    _modMoteurCtrl.dispose();
    _typeMoteurCtrl.dispose();
    _anneeCtrl.dispose();
    _transmissionCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);

    await StorageService.saveConnectionSettings(
      _ipCtrl.text.trim(),
      _portCtrl.text.trim(),
    );
    await StorageService.saveVehicleInfo(
      _marqueCtrl.text.trim(),
      _modeleCtrl.text.trim(),
      _typeMoteurCtrl.text.trim(),
      _modMoteurCtrl.text.trim(),
      _anneeCtrl.text.trim(),
      '',
      _transmissionCtrl.text.trim(),
      '',
      '',
      '',
    );
    await StorageService.markSetupDone();

    if (mounted) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const MainScreen()),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 32),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // ── Logo / En-tête ────────────────────────────────────────
                Center(
                  child: Column(
                    children: [
                      Container(
                        width: 72,
                        height: 72,
                        decoration: BoxDecoration(
                          color: AppColors.accentCyan.withValues(alpha: 0.1),
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: AppColors.accentCyan.withValues(alpha: 0.4),
                            width: 2,
                          ),
                        ),
                        child: const Icon(
                          Icons.directions_car_outlined,
                          color: AppColors.accentCyan,
                          size: 34,
                        ),
                      ),
                      const SizedBox(height: 20),
                      const Text(
                        'SEDAI',
                        style: TextStyle(
                          color: AppColors.accentCyan,
                          fontSize: 26,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 4.0,
                        ),
                      ),
                      const SizedBox(height: 6),
                      const Text(
                        'CONFIGURATION INITIALE',
                        style: TextStyle(
                          color: AppColors.textSecondary,
                          fontSize: 12,
                          letterSpacing: 2.5,
                        ),
                      ),
                    ],
                  ),
                ).animate().fadeIn(duration: 500.ms),

                const SizedBox(height: 40),

                // ── Section connexion ─────────────────────────────────────
                _sectionHeader(Icons.wifi_outlined, 'CONNEXION RASPBERRY PI'),
                const SizedBox(height: 16),

                _buildField(
                  controller: _ipCtrl,
                  label: 'Adresse IP',
                  hint: '192.168.4.1',
                  keyboardType:
                      const TextInputType.numberWithOptions(decimal: true),
                  validator: (v) =>
                      (v == null || v.trim().isEmpty) ? 'IP requise' : null,
                ),
                const SizedBox(height: 14),
                _buildField(
                  controller: _portCtrl,
                  label: 'Port WebSocket',
                  hint: '8765',
                  keyboardType: TextInputType.number,
                  validator: (v) {
                    if (v == null || v.trim().isEmpty) return 'Port requis';
                    final p = int.tryParse(v.trim());
                    if (p == null || p < 1 || p > 65535) {
                      return 'Port invalide (1 – 65535)';
                    }
                    return null;
                  },
                ),

                const SizedBox(height: 32),

                // ── Section véhicule ──────────────────────────────────────
                _sectionHeader(
                    Icons.directions_car_outlined, 'INFORMATIONS VÉHICULE'),
                const SizedBox(height: 6),
                const Text(
                  'Ces informations sont transmises à l\'IA pour affiner les diagnostics.',
                  style: TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 12,
                    height: 1.5,
                  ),
                ),
                const SizedBox(height: 16),

                _buildField(
                  controller: _marqueCtrl,
                  label: 'Marque',
                  hint: 'Ex : Toyota, Honda, Suzuki…',
                  validator: (v) =>
                      (v == null || v.trim().isEmpty) ? 'Marque requise' : null,
                ),
                const SizedBox(height: 14),
                _buildField(
                  controller: _modeleCtrl,
                  label: 'Modèle du véhicule',
                  hint: 'Ex : Corolla, CR-V, Swift…',
                  validator: (v) =>
                      (v == null || v.trim().isEmpty) ? 'Modèle requis' : null,
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    Expanded(
                      child: _buildField(
                        controller: _anneeCtrl,
                        label: 'Année',
                        hint: 'Ex: 2018',
                        keyboardType: TextInputType.number,
                        validator: (v) => (v == null || v.trim().isEmpty) ? 'Requise' : null,
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      flex: 2,
                      child: _buildField(
                        controller: _transmissionCtrl,
                        label: 'Transmission',
                        hint: 'Manuelle, Auto...',
                        validator: (v) => (v == null || v.trim().isEmpty) ? 'Requise' : null,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),

                // Sous-titre moteur
                const Text(
                  'MOTEUR',
                  style: TextStyle(
                    color: AppColors.accentCyan,
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 2.0,
                  ),
                ),
                const SizedBox(height: 10),

                _buildField(
                  controller: _modMoteurCtrl,
                  label: 'Modèle du moteur',
                  hint: 'Ex : 1ZZ-FE, K20A, OM651…',
                  validator: (v) => (v == null || v.trim().isEmpty)
                      ? 'Modèle du moteur requis'
                      : null,
                ),
                const SizedBox(height: 14),
                _buildField(
                  controller: _typeMoteurCtrl,
                  label: 'Type de moteur',
                  hint: 'Ex : 1.8L essence, 2.0L diesel turbo…',
                  validator: (v) => (v == null || v.trim().isEmpty)
                      ? 'Type de moteur requis'
                      : null,
                ),

                const SizedBox(height: 40),

                SizedBox(
                  width: double.infinity,
                  height: 54,
                  child: ElevatedButton(
                    onPressed: _saving ? null : _save,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.accentCyan,
                      foregroundColor: AppColors.background,
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12)),
                    ),
                    child: _saving
                        ? const SizedBox(
                            width: 22,
                            height: 22,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: AppColors.background,
                            ),
                          )
                        : const Text(
                            'DÉMARRER',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w700,
                              letterSpacing: 2.5,
                            ),
                          ),
                  ),
                ).animate().slideY(begin: 0.2, delay: 200.ms),

                const SizedBox(height: 16),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _sectionHeader(IconData icon, String text) {
    return Row(
      children: [
        Icon(icon, color: AppColors.accentCyan, size: 16),
        const SizedBox(width: 8),
        Text(
          text,
          style: const TextStyle(
            color: AppColors.accentCyan,
            fontSize: 11,
            fontWeight: FontWeight.w700,
            letterSpacing: 2.0,
          ),
        ),
      ],
    );
  }

  Widget _buildField({
    required TextEditingController controller,
    required String label,
    required String hint,
    TextInputType? keyboardType,
    String? Function(String?)? validator,
  }) {
    return TextFormField(
      controller: controller,
      keyboardType: keyboardType,
      style: const TextStyle(color: AppColors.textPrimary, fontSize: 15),
      decoration: InputDecoration(labelText: label, hintText: hint),
      validator: validator,
    );
  }
}
