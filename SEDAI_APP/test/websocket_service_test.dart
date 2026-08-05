import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sedai_diagnostic/services/storage_service.dart';
import 'package:sedai_diagnostic/services/websocket_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('connect handles unreachable websocket without throwing', () async {
    SharedPreferences.setMockInitialValues({});
    await StorageService.init();
    await StorageService.saveConnectionSettings('invalid-host', '80');

    final service = WebSocketService();
    Object? capturedError;

    await runZonedGuarded(() async {
      service.connect();
      await Future.delayed(const Duration(milliseconds: 500));
    }, (error, stackTrace) {
      capturedError = error;
    });

    expect(capturedError, isNull,
        reason: 'connect should not raise uncaught async errors');

    service.dispose();
  });
}
