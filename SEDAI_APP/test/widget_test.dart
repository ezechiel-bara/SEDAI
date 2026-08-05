import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('Tailsoft Dashboard loads and displays',
      (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const TailsoftApp() as Widget);

    // Verify that the app title is displayed.
    expect(find.text('DASH-BORD IA'), findsOneWidget);

    // Verify that gauges are rendered.
    expect(find.byType(CustomPaint), findsWidgets);
  });
}

class TailsoftApp {
  const TailsoftApp();
}
