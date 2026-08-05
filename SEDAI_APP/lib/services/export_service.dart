import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';
import 'package:intl/intl.dart';
import '../models/diagnosis_record.dart';

class ExportService {
  static Future<void> exportDiagnosisAsPdf(DiagnosisRecord record) async {
    final pdf = pw.Document();
    final dateStr = DateFormat('dd/MM/yyyy  HH:mm').format(record.timestamp);

    pdf.addPage(
      pw.MultiPage(
        pageFormat: PdfPageFormat.a4,
        margin: const pw.EdgeInsets.all(32),
        build: (pw.Context context) {
          return [
            // Header
            pw.Header(
              level: 0,
              child: pw.Row(
                mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
                children: [
                  pw.Text(
                    'RAPPORT DE DIAGNOSTIC',
                    style: pw.TextStyle(
                      fontSize: 24,
                      fontWeight: pw.FontWeight.bold,
                      color: PdfColors.blueGrey800,
                    ),
                  ),
                  pw.Text(
                    'SEDAI',
                    style: pw.TextStyle(
                      fontSize: 20,
                      fontWeight: pw.FontWeight.bold,
                      color: PdfColors.lightBlue700,
                    ),
                  ),
                ],
              ),
            ),
            pw.SizedBox(height: 20),

            // Vehicle Info Container
            pw.Container(
              padding: const pw.EdgeInsets.all(16),
              decoration: pw.BoxDecoration(
                color: PdfColors.grey100,
                borderRadius: const pw.BorderRadius.all(pw.Radius.circular(8)),
                border: pw.Border.all(color: PdfColors.grey300),
              ),
              child: pw.Column(
                crossAxisAlignment: pw.CrossAxisAlignment.start,
                children: [
                  _buildMetaRow('VÉHICULE', record.vehicleLabel),
                  pw.SizedBox(height: 10),
                  _buildMetaRow('DATE DU DIAGNOSTIC', dateStr),
                ],
              ),
            ),
            pw.SizedBox(height: 30),

            // AI Report Title
            pw.Text(
              'RAPPORT IA LOCALE',
              style: pw.TextStyle(
                fontSize: 14,
                fontWeight: pw.FontWeight.bold,
                color: PdfColors.blueGrey600,
                letterSpacing: 1.2,
              ),
            ),
            pw.SizedBox(height: 10),
            pw.Divider(color: PdfColors.grey400),
            pw.SizedBox(height: 10),

            // Full content
            pw.Text(
              record.content,
              style: const pw.TextStyle(
                fontSize: 12,
                lineSpacing: 1.5,
                color: PdfColors.black,
              ),
            ),
          ];
        },
      ),
    );

    // Prompt user to save/share the PDF
    await Printing.sharePdf(
      bytes: await pdf.save(),
      filename: 'Diagnostic_${record.vehicleLabel.replaceAll(" ", "_")}_${DateFormat('yyyyMMdd_HHmm').format(record.timestamp)}.pdf',
    );
  }

  static pw.Widget _buildMetaRow(String label, String value) {
    return pw.Row(
      crossAxisAlignment: pw.CrossAxisAlignment.start,
      children: [
        pw.Expanded(
          flex: 2,
          child: pw.Text(
            label,
            style: pw.TextStyle(
              fontSize: 10,
              fontWeight: pw.FontWeight.bold,
              color: PdfColors.grey600,
            ),
          ),
        ),
        pw.Expanded(
          flex: 5,
          child: pw.Text(
            value,
            style: pw.TextStyle(
              fontSize: 12,
              fontWeight: pw.FontWeight.bold,
              color: PdfColors.black,
            ),
          ),
        ),
      ],
    );
  }
}
