// ESTE ARQUIVO E UM SUBSTITUTO TEMPORARIO.
//
// O comando `flutterfire configure` (veja o README) sobrescreve este arquivo
// com as credenciais do seu projeto Firebase. Enquanto isso nao acontece, o
// app funciona normalmente sem notificacoes push: os alertas de proximidade
// aparecem dentro do app, a partir da resposta do backend.

import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;

class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    throw UnsupportedError(
      'Firebase ainda nao configurado: rode "flutterfire configure".',
    );
  }
}
