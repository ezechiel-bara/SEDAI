import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:intl/intl.dart';
import '../core/constants.dart';
import '../models/diagnosis_record.dart';
import '../services/storage_service.dart';
import '../services/export_service.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<DiagnosisRecord> _records = [];

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  void _loadHistory() {
    setState(() => _records = StorageService.getHistory());
  }

  Future<void> _deleteRecord(DiagnosisRecord record) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        title: const Text('Supprimer ce diagnostic ?',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 16)),
        content: const Text(
          'Cette action est irréversible.',
          style: TextStyle(color: AppColors.textSecondary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('ANNULER',
                style: TextStyle(color: AppColors.textSecondary)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('SUPPRIMER',
                style: TextStyle(color: AppColors.dangerRed)),
          ),
        ],
      ),
    );
    if (confirm == true) {
      await StorageService.deleteRecord(record.id);
      _loadHistory();
    }
  }

  Future<void> _clearAll() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        title: const Text('Vider tout l\'historique ?',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 16)),
        content: Text(
          '${_records.length} diagnostic(s) seront supprimés définitivement.',
          style: const TextStyle(color: AppColors.textSecondary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('ANNULER',
                style: TextStyle(color: AppColors.textSecondary)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('TOUT EFFACER',
                style: TextStyle(color: AppColors.dangerRed)),
          ),
        ],
      ),
    );
    if (confirm == true) {
      await StorageService.clearHistory();
      _loadHistory();
    }
  }

  void _openDetail(DiagnosisRecord record) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => _HistoryDetailScreen(record: record),
      ),
    ).then((_) => _loadHistory());
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // ── En-tête avec compteur et bouton vider ─────────────────────────
        Container(
          padding: const EdgeInsets.fromLTRB(16, 12, 12, 12),
          decoration: const BoxDecoration(
            color: AppColors.surface,
            border: Border(
              bottom: BorderSide(color: AppColors.cardBorder),
            ),
          ),
          child: Row(
            children: [
              const Icon(Icons.history_outlined,
                  color: AppColors.accentCyan, size: 18),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  '${_records.length} DIAGNOSTIC(S) SAUVEGARDÉ(S)',
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1.5,
                  ),
                ),
              ),
              if (_records.isNotEmpty)
                TextButton.icon(
                  onPressed: _clearAll,
                  icon: const Icon(Icons.delete_sweep_outlined,
                      color: AppColors.dangerRed, size: 16),
                  label: const Text('VIDER',
                      style: TextStyle(
                          color: AppColors.dangerRed,
                          fontSize: 11,
                          letterSpacing: 1.2)),
                  style: TextButton.styleFrom(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 10, vertical: 6),
                  ),
                ),
            ],
          ),
        ),

        // ── Liste des diagnostics ─────────────────────────────────────────
        Expanded(
          child: _records.isEmpty
              ? _buildEmptyState()
              : RefreshIndicator(
                  onRefresh: () async => _loadHistory(),
                  color: AppColors.accentCyan,
                  backgroundColor: AppColors.surface,
                  child: ListView.separated(
                    padding: const EdgeInsets.fromLTRB(14, 12, 14, 20),
                    itemCount: _records.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 10),
                    itemBuilder: (_, index) {
                      final record = _records[index];
                      return _RecordCard(
                        record: record,
                        index: index,
                        onTap: () => _openDetail(record),
                        onDelete: () => _deleteRecord(record),
                      );
                    },
                  ),
                ),
        ),
      ],
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.inbox_outlined,
              color: AppColors.textMuted.withValues(alpha: 0.6), size: 56),
          const SizedBox(height: 16),
          const Text(
            'AUCUN DIAGNOSTIC SAUVEGARDÉ',
            style: TextStyle(
              color: AppColors.textSecondary,
              fontSize: 12,
              letterSpacing: 2.0,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Lancez un diagnostic depuis le Dashboard\npuis sauvegardez-le.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: AppColors.textMuted,
              fontSize: 13,
              height: 1.6,
            ),
          ),
        ],
      ).animate().fadeIn(delay: 200.ms),
    );
  }
}

// ── Carte de diagnostic ───────────────────────────────────────────────────────
class _RecordCard extends StatelessWidget {
  final DiagnosisRecord record;
  final int index;
  final VoidCallback onTap;
  final VoidCallback onDelete;

  const _RecordCard({
    required this.record,
    required this.index,
    required this.onTap,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final dateStr =
        DateFormat('dd/MM/yyyy  HH:mm').format(record.timestamp);

    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.cardBorder),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // En-tête : véhicule + date + supprimer
            Row(
              children: [
                const Icon(Icons.directions_car_outlined,
                    color: AppColors.textSecondary, size: 14),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    record.vehicleLabel,
                    style: const TextStyle(
                      color: AppColors.accentCyan,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.5,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  dateStr,
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 10,
                  ),
                ),
                const SizedBox(width: 4),
                GestureDetector(
                  onTap: onDelete,
                  child: const Padding(
                    padding: EdgeInsets.only(left: 8),
                    child: Icon(Icons.close_rounded,
                        color: AppColors.textMuted, size: 16),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            const Divider(height: 1),
            const SizedBox(height: 10),
            // Aperçu du contenu
            Text(
              record.preview,
              style: const TextStyle(
                color: AppColors.textPrimary,
                fontSize: 13,
                height: 1.55,
              ),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 10),
            // Lire la suite
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                Text(
                  'VOIR COMPLET',
                  style: TextStyle(
                    color: AppColors.accentCyan.withValues(alpha: 0.8),
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1.5,
                  ),
                ),
                const SizedBox(width: 4),
                Icon(Icons.arrow_forward_ios_rounded,
                    color: AppColors.accentCyan.withValues(alpha: 0.8), size: 10),
              ],
            ),
          ],
        ),
      ).animate().fadeIn(delay: Duration(milliseconds: 40 * index)),
    );
  }
}

// ── Écran de détail d'un diagnostic sauvegardé ───────────────────────────────
class _HistoryDetailScreen extends StatelessWidget {
  final DiagnosisRecord record;

  const _HistoryDetailScreen({required this.record});

  @override
  Widget build(BuildContext context) {
    final dateStr =
        DateFormat('dd/MM/yyyy  HH:mm').format(record.timestamp);

    return Scaffold(
      appBar: AppBar(
        title: const Text('DÉTAIL DIAGNOSTIC'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded,
              color: AppColors.accentCyan, size: 18),
          onPressed: () => Navigator.pop(context),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.download_rounded, color: AppColors.accentCyan),
            tooltip: 'Télécharger / Exporter',
            onPressed: () => ExportService.exportDiagnosisAsPdf(record),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Infos véhicule + date
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.cardBorder),
              ),
              child: Column(
                children: [
                  _metaRow(Icons.directions_car_outlined,
                      'VÉHICULE', record.vehicleLabel),
                  const SizedBox(height: 10),
                  _metaRow(Icons.access_time_outlined, 'DATE', dateStr),
                ],
              ),
            ),
            const SizedBox(height: 20),
            // Rapport complet
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
                  'RAPPORT IA LOCALE',
                  style: TextStyle(
                    color: AppColors.textSecondary,
                    fontWeight: FontWeight.w700,
                    fontSize: 10,
                    letterSpacing: 1.8,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: AppColors.cardBorder),
              ),
              child: SelectableText(
                record.content,
                style: const TextStyle(
                  fontSize: 15,
                  height: 1.7,
                  color: AppColors.textPrimary,
                  letterSpacing: 0.3,
                ),
              ),
            ),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              height: 50,
              child: ElevatedButton.icon(
                onPressed: () => Navigator.pop(context),
                icon: const Icon(Icons.arrow_back_outlined, size: 18),
                label: const Text('RETOUR À L\'HISTORIQUE'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.surfaceAlt,
                  foregroundColor: AppColors.textSecondary,
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10)),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _metaRow(IconData icon, String label, String value) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
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
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                )),
          ],
        ),
      ],
    );
  }
}
