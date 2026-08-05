import 'dart:async';
import 'package:flutter/material.dart';
import '../core/constants.dart';
import '../services/websocket_service.dart';

/// États possibles de l'interface vocale
enum _VoiceState { listening, processing, answered }

/// BottomSheet de l'assistant vocal SEDAI.
/// S'ouvre quand le PTT est activé, affiche la transcription
/// et la réponse de l'IA, puis se ferme automatiquement.
class VoiceAssistantSheet extends StatefulWidget {
  final WebSocketService wsService;

  const VoiceAssistantSheet({super.key, required this.wsService});

  @override
  State<VoiceAssistantSheet> createState() => _VoiceAssistantSheetState();
}

class _VoiceAssistantSheetState extends State<VoiceAssistantSheet>
    with SingleTickerProviderStateMixin {

  _VoiceState _state = _VoiceState.listening;
  String _userText = '';
  String _aiText = '';

  StreamSubscription? _transSub;
  StreamSubscription? _diagSub;
  StreamSubscription? _diagSub2;
  Timer? _autoCloseTimer;

  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();

    // Animation de pulsation du micro
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat(reverse: true);

    _pulseAnimation = Tween<double>(begin: 0.85, end: 1.1).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );

    // 1. Écouter la transcription (ce que dit l'utilisateur)
    _transSub = widget.wsService.transcriptionStream.listen((text) {
      if (mounted) {
        setState(() {
          _userText = text;
          _state = _VoiceState.processing;
        });
        _pulseController.stop();
      }
    });

    // 2. Écouter la réponse IA (diagnostic complet)
    _diagSub = widget.wsService.diagnosisStream.listen((result) {
      if (mounted) {
        setState(() {
          _aiText = result.content;
          _state = _VoiceState.answered;
        });
        _scheduleAutoClose();
      }
    });

    // 3. Écouter aussi les réponses chat (conversation libre)
    _diagSub2 = widget.wsService.chatStream.listen((data) {
      final text = data['texte'] as String? ?? '';
      final source = data['source'] as String? ?? '';
      // On ne réaffiche que les réponses vocales (pas les messages du chat textuel)
      if (mounted && text.isNotEmpty && source == 'voice') {
        setState(() {
          _aiText = text;
          _state = _VoiceState.answered;
        });
        _scheduleAutoClose();
      }
    });
  }

  void _scheduleAutoClose() {
    _autoCloseTimer?.cancel();
    // Fermeture automatique après 12 secondes (assez pour lire un rapport court)
    _autoCloseTimer = Timer(const Duration(seconds: 12), () {
      if (mounted) Navigator.of(context).pop();
    });
  }

  @override
  void dispose() {
    _transSub?.cancel();
    _diagSub?.cancel();
    _diagSub2?.cancel();
    _autoCloseTimer?.cancel();
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        border: Border(
          top: BorderSide(color: AppColors.cardBorder, width: 1.5),
        ),
      ),
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Poignée de glissement
          Container(
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: AppColors.textMuted,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(height: 20),

          // Header
          Row(
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: _state == _VoiceState.listening
                      ? AppColors.dangerRed
                      : (_state == _VoiceState.processing
                          ? AppColors.alertOrange
                          : AppColors.accentGreen),
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                _state == _VoiceState.listening
                    ? "SEDAI vous écoute…"
                    : (_state == _VoiceState.processing
                        ? "SEDAI analyse…"
                        : "SEDAI a répondu"),
                style: const TextStyle(
                  color: AppColors.textSecondary,
                  fontSize: 11,
                  letterSpacing: 1.5,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const Spacer(),
              GestureDetector(
                onTap: () => Navigator.of(context).pop(),
                child: const Icon(Icons.close,
                    color: AppColors.textSecondary, size: 20),
              ),
            ],
          ),
          const SizedBox(height: 24),

          // Corps central
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 350),
            child: _buildBody(),
          ),
          const SizedBox(height: 8),
        ],
      ),
    );
  }

  Widget _buildBody() {
    switch (_state) {
      case _VoiceState.listening:
        return _buildListeningState();
      case _VoiceState.processing:
        return _buildProcessingState();
      case _VoiceState.answered:
        return _buildAnsweredState();
    }
  }

  // --- État 1 : Écoute ---
  Widget _buildListeningState() {
    return Column(
      key: const ValueKey('listening'),
      children: [
        ScaleTransition(
          scale: _pulseAnimation,
          child: Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: AppColors.dangerRed.withValues(alpha: 0.15),
              border: Border.all(
                  color: AppColors.dangerRed.withValues(alpha: 0.6), width: 2),
            ),
            child: const Icon(Icons.mic, color: AppColors.dangerRed, size: 34),
          ),
        ),
        const SizedBox(height: 16),
        const Text(
          "Parlez maintenant…",
          style: TextStyle(
            color: AppColors.textPrimary,
            fontSize: 16,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }

  // --- État 2 : Traitement ---
  Widget _buildProcessingState() {
    return Column(
      key: const ValueKey('processing'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _UserBubble(text: _userText),
        const SizedBox(height: 12),
        const _AiBubble(isLoading: true),
      ],
    );
  }

  // --- État 3 : Réponse reçue ---
  Widget _buildAnsweredState() {
    return Column(
      key: const ValueKey('answered'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _UserBubble(text: _userText),
        const SizedBox(height: 12),
        _AiBubble(text: _aiText, isLoading: false),
        const SizedBox(height: 12),
        const Center(
          child: Text(
            "Fermeture automatique dans 5s…",
            style: TextStyle(
              color: AppColors.textMuted,
              fontSize: 11,
              fontStyle: FontStyle.italic,
            ),
          ),
        ),
      ],
    );
  }
}

// ─── Bulle de message utilisateur ──────────────────────────────────────────
class _UserBubble extends StatelessWidget {
  final String text;
  const _UserBubble({required this.text});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        Flexible(
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: BoxDecoration(
              color: AppColors.accentCyan.withValues(alpha: 0.12),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(16),
                topRight: Radius.circular(4),
                bottomLeft: Radius.circular(16),
                bottomRight: Radius.circular(16),
              ),
              border: Border.all(
                  color: AppColors.accentCyan.withValues(alpha: 0.3), width: 1),
            ),
            child: Text(
              '"$text"',
              style: const TextStyle(
                color: AppColors.textPrimary,
                fontSize: 14,
                fontStyle: FontStyle.italic,
              ),
            ),
          ),
        ),
        const SizedBox(width: 10),
        const CircleAvatar(
          radius: 14,
          backgroundColor: AppColors.accentCyan,
          child: Icon(Icons.person, color: AppColors.background, size: 16),
        ),
      ],
    );
  }
}

// ─── Bulle de réponse IA ───────────────────────────────────────────────────
class _AiBubble extends StatelessWidget {
  final String? text;
  final bool isLoading;
  const _AiBubble({this.text, required this.isLoading});

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 28,
          height: 28,
          decoration: const BoxDecoration(
            shape: BoxShape.circle,
            gradient: LinearGradient(
              colors: [AppColors.accentCyan, AppColors.accentGreen],
            ),
          ),
          child: const Center(
            child: Text(
              'S',
              style: TextStyle(
                color: AppColors.background,
                fontWeight: FontWeight.w900,
                fontSize: 14,
              ),
            ),
          ),
        ),
        const SizedBox(width: 10),
        Flexible(
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: AppColors.surfaceAlt,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(4),
                topRight: Radius.circular(16),
                bottomLeft: Radius.circular(16),
                bottomRight: Radius.circular(16),
              ),
              border: Border.all(color: AppColors.cardBorder, width: 1),
            ),
            child: isLoading
                ? const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      _Dot(delay: 0),
                      _Dot(delay: 200),
                      _Dot(delay: 400),
                      SizedBox(width: 8),
                      Text(
                        "Analyse en cours…",
                        style: TextStyle(
                            color: AppColors.textSecondary, fontSize: 13),
                      ),
                    ],
                  )
                : Text(
                    text ?? '',
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 14,
                      height: 1.5,
                    ),
                  ),
          ),
        ),
      ],
    );
  }
}

// ─── Point animé pour l'indicateur de chargement ──────────────────────────
class _Dot extends StatefulWidget {
  final int delay;
  const _Dot({required this.delay});

  @override
  State<_Dot> createState() => _DotState();
}

class _DotState extends State<_Dot> with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _anim;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 600))
      ..repeat(reverse: true);
    _anim = Tween<double>(begin: 0.3, end: 1.0).animate(_ctrl);

    // Délai pour désynchroniser les points
    Future.delayed(Duration(milliseconds: widget.delay), () {
      if (mounted) _ctrl.forward();
    });
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 4),
      child: FadeTransition(
        opacity: _anim,
        child: Container(
          width: 7,
          height: 7,
          decoration: const BoxDecoration(
            color: AppColors.accentCyan,
            shape: BoxShape.circle,
          ),
        ),
      ),
    );
  }
}
