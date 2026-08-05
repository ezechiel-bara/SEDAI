import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'core/theme.dart';
import 'screens/setup_screen.dart';
import 'screens/main_screen.dart';
import 'services/storage_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Orientation : portrait + paysage autorisés
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.landscapeLeft,
    DeviceOrientation.landscapeRight,
  ]);

  // Barre de statut système transparente
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
      systemNavigationBarColor: Color(0xFF0E1A2E),
      systemNavigationBarIconBrightness: Brightness.light,
    ),
  );

  // Initialiser le stockage local
  await StorageService.init();

  runApp(const AutoJapanApp());
}

class AutoJapanApp extends StatelessWidget {
  const AutoJapanApp({super.key});

  @override
  Widget build(BuildContext context) {
    final isFirstLaunch = StorageService.isFirstLaunch();

    return MaterialApp(
      title: 'SEDAI Diagnostic',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      // Premier lancement → écran de configuration, sinon → app principale
      home: isFirstLaunch ? const SetupScreen() : const MainScreen(),
    );
  }
}
