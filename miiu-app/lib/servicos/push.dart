import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

import '../firebase_options.dart';
import 'api.dart';

/// Notificacoes push pelo Firebase Cloud Messaging.
///
/// Opcional: sem o Firebase configurado (flutterfire configure), o app segue
/// funcionando e mostra os alertas de proximidade apenas quando esta aberto.
/// Com o app em primeiro plano, as notificacoes do FCM nao sao exibidas pelo
/// sistema; nesse caso quem mostra o alerta e o proprio app, a partir da
/// resposta do backend, o que evita alerta em dobro.
class Push {
  static bool disponivel = false;
  static String? token;
  static String? erro;

  static Future<void> iniciar() async {
    try {
      await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
      final mensageria = FirebaseMessaging.instance;
      await mensageria.requestPermission();
      token = await mensageria.getToken();
      disponivel = token != null;
      mensageria.onTokenRefresh.listen((novo) {
        token = novo;
        unawaited(_registrar());
      });
    } catch (e) {
      disponivel = false;
      erro = e.toString();
    }
    // Registra o aparelho no backend sem atrasar a abertura do app
    unawaited(_registrar());
  }

  static Future<void> _registrar() async {
    try {
      await Api.registrarDispositivo(tokenFcm: token);
    } catch (_) {
      // servidor fora do ar: o registro e refeito na proxima abertura
    }
  }
}
