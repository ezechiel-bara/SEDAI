import 'dart:async';
import 'package:flutter/material.dart';
import '../core/constants.dart';
import '../services/websocket_service.dart';
import '../models/chat_message_model.dart';

class ChatScreen extends StatefulWidget {
  final WebSocketService wsService;
  final bool autoStartVoice;

  const ChatScreen({super.key, required this.wsService, this.autoStartVoice = false});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final List<ChatMessage> _messages = [];
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  StreamSubscription? _chatSub;
  StreamSubscription? _dataSub;
  double _currentSpeed = 0;
  bool _isTyping = false;
  bool _isVoiceActive = false;
  StreamSubscription? _transSub;

  @override
  void initState() {
    super.initState();

    // Ajouter un message de bienvenue de l'IA
    _messages.add(ChatMessage(
      text: "Bonjour, je suis SEDAI. Comment puis-je vous aider ?",
      isUser: false,
      timestamp: DateTime.now(),
    ));

    if (widget.autoStartVoice) {
      // Démarre la voix après le 1er frame pour s'assurer que UI est monté
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _toggleVoice();
      });
    }

    _chatSub = widget.wsService.chatStream.listen((chatData) {
      if (mounted) {
        final text = chatData['texte'] as String?;
        // Ne pas afficher si c'est vide ou si c'est le même message
        if (text != null && text.isNotEmpty) {
          // Check if the last AI message is not the same (prevent duplicates from broadcast loop)
          bool isDuplicate = false;
          for (var i = _messages.length - 1; i >= 0; i--) {
            if (!_messages[i].isUser) {
              if (_messages[i].text == text) {
                isDuplicate = true;
              }
              break;
            }
          }

          if (!isDuplicate) {
            // Un petit délai garantit que si la transcription et la réponse arrivent
            // exactement au même moment, la transcription s'affiche EN PREMIER.
            Future.delayed(const Duration(milliseconds: 50), () {
              if (mounted) {
                setState(() {
                  _messages.add(ChatMessage(
                    text: text,
                    isUser: false,
                    timestamp: DateTime.now(),
                  ));
                  _isTyping = false;
                });
                _scrollToBottom();
              }
            });
          }
        }
      }
    });

    _dataSub = widget.wsService.dataStream.listen((data) {
      if (mounted) {
        setState(() {
          _currentSpeed = data.vitesse;
        });
      }
    });

    _transSub = widget.wsService.transcriptionStream.listen((text) {
      if (mounted && text.isNotEmpty) {
        setState(() {
          _messages.add(ChatMessage(
            text: text,
            isUser: true,
            timestamp: DateTime.now(),
          ));
          _isTyping = true;
          _isVoiceActive = false;
        });
        _scrollToBottom();
      }
    });
  }

  @override
  void dispose() {
    _chatSub?.cancel();
    _dataSub?.cancel();
    _transSub?.cancel();
    _textController.dispose();
    _scrollController.dispose();
    if (_isVoiceActive) {
      widget.wsService.deactivateVoice();
    }
    super.dispose();
  }

  void _sendMessage() {
    final text = _textController.text.trim();
    if (text.isNotEmpty) {
      setState(() {
        _messages.add(ChatMessage(
          text: text,
          isUser: true,
          timestamp: DateTime.now(),
        ));
        _isTyping = true;
      });
      widget.wsService.sendChatMessage(text);
      _textController.clear();
      _scrollToBottom();
    }
  }

  void _toggleVoice() {
    setState(() {
      _isVoiceActive = !_isVoiceActive;
    });
    if (_isVoiceActive) {
      widget.wsService.activateVoice();
    } else {
      widget.wsService.deactivateVoice();
    }
  }

  void _scrollToBottom() {
    Future.delayed(const Duration(milliseconds: 100), () {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Widget _buildMessage(ChatMessage message) {
    Widget bubble = Container(
      margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 12),
      padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 14),
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.8,
      ),
      decoration: BoxDecoration(
        color: message.isUser ? AppColors.accentCyan.withValues(alpha: 0.2) : AppColors.surfaceAlt,
        borderRadius: BorderRadius.circular(16).copyWith(
          bottomRight: message.isUser ? const Radius.circular(0) : const Radius.circular(16),
          bottomLeft: !message.isUser ? const Radius.circular(0) : const Radius.circular(16),
        ),
        border: Border.all(
          color: message.isUser ? AppColors.accentCyan.withValues(alpha: 0.5) : AppColors.cardBorder,
        ),
      ),
      child: Text(
        message.text,
        style: const TextStyle(color: AppColors.textPrimary, fontSize: 14),
      ),
    );

    if (message.isUser) {
      // Permet à l'utilisateur de cliquer sur son propre message pour le corriger
      bubble = GestureDetector(
        onTap: () {
          setState(() {
            _textController.text = message.text;
            // Place le curseur à la fin
            _textController.selection = TextSelection.fromPosition(
              TextPosition(offset: message.text.length),
            );
          });
        },
        child: bubble,
      );
    }

    return Align(
      alignment: message.isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: bubble,
    );
  }

  @override
  Widget build(BuildContext context) {
    final isLocked = _currentSpeed > 5; // Seuil 5 km/h pour éviter micro-fluctuations OBD

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text(
          'CHAT SEDAI',
          style: TextStyle(
            color: AppColors.accentCyan,
            fontSize: 14,
            fontWeight: FontWeight.w700,
            letterSpacing: 2.0,
          ),
        ),
        backgroundColor: AppColors.surface,
        iconTheme: const IconThemeData(color: AppColors.accentCyan),
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.only(top: 16, bottom: 16),
              itemCount: _messages.length + (_isTyping ? 1 : 0),
              itemBuilder: (context, index) {
                if (index == _messages.length && _isTyping) {
                  return Align(
                    alignment: Alignment.centerLeft,
                    child: Container(
                      margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 12),
                      padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 18),
                      decoration: BoxDecoration(
                        color: AppColors.surfaceAlt,
                        borderRadius: BorderRadius.circular(16).copyWith(
                          bottomLeft: const Radius.circular(0),
                        ),
                        border: Border.all(color: AppColors.cardBorder),
                      ),
                      child: const SizedBox(
                        width: 40,
                        height: 20,
                        child: Center(
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: AppColors.accentCyan,
                          ),
                        ),
                      ),
                    ),
                  );
                }
                return _buildMessage(_messages[index]);
              },
            ),
          ),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: const BoxDecoration(
              color: AppColors.surface,
              border: Border(top: BorderSide(color: AppColors.cardBorder)),
            ),
            child: isLocked
                ? const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.lock, color: AppColors.alertOrange, size: 20),
                      SizedBox(width: 8),
                      Text(
                        "Chat textuel désactivé en roulant",
                        style: TextStyle(color: AppColors.alertOrange, fontWeight: FontWeight.bold),
                      ),
                    ],
                  )
                : Row(
                    children: [
                      CircleAvatar(
                        backgroundColor: _isVoiceActive ? AppColors.dangerRed : AppColors.surfaceAlt,
                        child: IconButton(
                          icon: Icon(
                            _isVoiceActive ? Icons.mic : Icons.mic_none,
                            color: _isVoiceActive ? AppColors.background : AppColors.accentCyan,
                          ),
                          onPressed: _toggleVoice,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: TextField(
                          controller: _textController,
                          style: const TextStyle(color: AppColors.textPrimary),
                          decoration: InputDecoration(
                            hintText: _isVoiceActive ? 'SEDAI vous écoute...' : 'Posez votre question...',
                            hintStyle: const TextStyle(color: AppColors.textSecondary),
                            filled: true,
                            fillColor: AppColors.surfaceAlt,
                            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(24),
                              borderSide: BorderSide.none,
                            ),
                          ),
                          onSubmitted: (_) => _sendMessage(),
                          enabled: !_isVoiceActive,
                        ),
                      ),
                      const SizedBox(width: 8),
                      CircleAvatar(
                        backgroundColor: _isVoiceActive ? AppColors.surfaceAlt : AppColors.accentCyan,
                        child: IconButton(
                          icon: Icon(Icons.send, color: _isVoiceActive ? AppColors.textMuted : AppColors.background),
                          onPressed: _isVoiceActive ? null : _sendMessage,
                        ),
                      ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}
