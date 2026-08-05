import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../core/constants.dart';
import '../services/websocket_service.dart';
import 'chat_screen.dart';
import 'dashboard_screen.dart';
import 'history_screen.dart';
import 'settings_screen.dart';

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  final WebSocketService _ws = WebSocketService();
  int _currentIndex = 0;
  ConnectionStatus _connStatus = ConnectionStatus.disconnected;

  @override
  void initState() {
    super.initState();
    _ws.connect();
    _ws.statusStream.listen((s) {
      if (mounted) setState(() => _connStatus = s);
    });
  }

  @override
  void dispose() {
    _ws.dispose();
    super.dispose();
  }

  // ── Builds des titres par onglet ──────────────────────────────────────────
  static const _titles = ['DASHBOARD', 'HISTORIQUE', 'PARAMÈTRES'];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            const Text(
              AppConstants.appTitle,
              style: TextStyle(
                color: AppColors.accentCyan,
                fontSize: 16,
                fontWeight: FontWeight.w700,
                letterSpacing: 4.0,
              ),
            ),
            Text(
              _titles[_currentIndex],
              style: const TextStyle(
                color: AppColors.textSecondary,
                fontSize: 9,
                letterSpacing: 2.5,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
        actions: [
          _StatusBadge(status: _connStatus),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => ChatScreen(wsService: _ws),
                ),
              );
            },
            child: Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(12),
                gradient: const LinearGradient(
                  colors: [
                    Color(0xFF00E5FF),
                    Color(0xFF00C853),
                    Color(0xFF6200EA),
                  ],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                boxShadow: [
                  BoxShadow(
                    color: const Color(0xFF00E5FF).withValues(alpha: 0.45),
                    blurRadius: 12,
                    spreadRadius: 1,
                    offset: const Offset(0, 3),
                  ),
                ],
              ),
              child: const Center(
                child: Icon(
                  Icons.auto_awesome, // Étoiles IA premium
                  color: Colors.white,
                  size: 20,
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: _buildBody(),
      bottomNavigationBar: _buildBottomNav(),
    );
  }

  Widget _buildBody() {
    // Utiliser IndexedStack pour garder les états des écrans
    return IndexedStack(
      index: _currentIndex,
      children: [
        DashboardScreen(wsService: _ws),
        const HistoryScreen(),
        SettingsScreen(
          wsService: _ws,
          onSettingsSaved: () {
            if (mounted) setState(() {});
          },
        ),
      ],
    );
  }

  Widget _buildBottomNav() {
    return Container(
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(
          top: BorderSide(color: AppColors.cardBorder, width: 1),
        ),
      ),
      child: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (i) => setState(() => _currentIndex = i),
        backgroundColor: Colors.transparent,
        elevation: 0,
        selectedLabelStyle: const TextStyle(
          fontSize: 9,
          fontWeight: FontWeight.w700,
          letterSpacing: 1.2,
        ),
        unselectedLabelStyle: const TextStyle(
          fontSize: 9,
          letterSpacing: 1.0,
        ),
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.speed_outlined),
            activeIcon: Icon(Icons.speed),
            label: 'DASHBOARD',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.history_outlined),
            activeIcon: Icon(Icons.history),
            label: 'HISTORIQUE',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.tune_outlined),
            activeIcon: Icon(Icons.tune),
            label: 'PARAMÈTRES',
          ),
        ],
      ),
    );
  }
}

// ── Badge de statut de connexion ──────────────────────────────────────────────
class _StatusBadge extends StatelessWidget {
  final ConnectionStatus status;
  const _StatusBadge({required this.status});

  @override
  Widget build(BuildContext context) {
    final (Color color, String label, IconData icon) = switch (status) {
      ConnectionStatus.connected => (
          AppColors.successGreen,
          'EN LIGNE',
          Icons.circle
        ),
      ConnectionStatus.connecting => (
          AppColors.alertOrange,
          'CONNECT…',
          Icons.circle
        ),
      ConnectionStatus.error => (AppColors.dangerRed, 'ERREUR', Icons.circle),
      ConnectionStatus.disconnected => (
          AppColors.textMuted,
          'HORS LIGNE',
          Icons.circle
        ),
    };

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 14),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 6),
          const SizedBox(width: 5),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 9,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.8,
            ),
          ),
        ],
      ),
    )
        .animate(
          onPlay: (c) => status == ConnectionStatus.connecting
              ? c.repeat(reverse: true)
              : c.stop(),
        )
        .fadeIn(duration: 300.ms);
  }
}
