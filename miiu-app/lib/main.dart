import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:latlong2/latlong.dart';

import 'estado.dart';
import 'modelos.dart';
import 'servicos/armazenamento.dart';
import 'servicos/geocerca.dart';
import 'servicos/push.dart';
import 'telas/configuracoes.dart';
import 'telas/inicio.dart';
import 'telas/minhas.dart';

final GlobalKey<ScaffoldMessengerState> mensageiro = GlobalKey<ScaffoldMessengerState>();

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Armazenamento.iniciar();
  runApp(const MiiuApp());
  // Depois do runApp: o pedido de permissao de notificacao nao atrasa a
  // primeira tela, e o app funciona mesmo sem o Firebase configurado
  unawaited(Push.iniciar());
}

class MiiuApp extends StatelessWidget {
  const MiiuApp({super.key});

  static const Color _semente = Color(0xFF2A78D6);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MIIU',
      debugShowCheckedModeBanner: false,
      scaffoldMessengerKey: mensageiro,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: _semente),
      ),
      darkTheme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: _semente, brightness: Brightness.dark),
      ),
      home: const Estrutura(),
    );
  }
}

/// Navegacao principal e exibicao dos alertas de proximidade.
class Estrutura extends StatefulWidget {
  const Estrutura({super.key});

  @override
  State<Estrutura> createState() => _EstruturaState();
}

class _EstruturaState extends State<Estrutura> {
  int _aba = 0;
  StreamSubscription<Alerta>? _assinaturaAlertas;

  @override
  void initState() {
    super.initState();
    _assinaturaAlertas = ServicoGeocerca.instancia.alertas.listen(_mostrarAlerta);
    Estado.focoNoMapa.addListener(_irParaMapa);
    // religa os alertas se o cidadao os deixou ligados na ultima vez
    if (Armazenamento.alertasAtivos) {
      WidgetsBinding.instance.addPostFrameCallback((_) => ServicoGeocerca.instancia.ligar());
    }
  }

  @override
  void dispose() {
    _assinaturaAlertas?.cancel();
    Estado.focoNoMapa.removeListener(_irParaMapa);
    super.dispose();
  }

  void _irParaMapa() {
    if (Estado.focoNoMapa.value != null && _aba != 0) setState(() => _aba = 0);
  }

  void _mostrarAlerta(Alerta alerta) {
    HapticFeedback.vibrate();
    SystemSound.play(SystemSoundType.alert);
    final messenger = mensageiro.currentState;
    if (messenger == null) return;
    messenger.clearMaterialBanners();
    messenger.showMaterialBanner(
      MaterialBanner(
        leading: const Icon(Icons.warning_amber_rounded, size: 32),
        content: Text('Atenção: ${alerta.mensagem}'),
        actions: [
          TextButton(
            onPressed: () {
              messenger.hideCurrentMaterialBanner();
              Estado.focoNoMapa.value = LatLng(alerta.latitude, alerta.longitude);
            },
            child: const Text('Ver no mapa'),
          ),
          TextButton(
            onPressed: messenger.hideCurrentMaterialBanner,
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _aba,
        children: const [TelaInicio(), TelaMinhas(), TelaConfiguracoes()],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _aba,
        onDestinationSelected: (i) => setState(() => _aba = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.map_outlined), selectedIcon: Icon(Icons.map), label: 'Mapa'),
          NavigationDestination(
            icon: Icon(Icons.receipt_long_outlined),
            selectedIcon: Icon(Icons.receipt_long),
            label: 'Meus reportes',
          ),
          NavigationDestination(icon: Icon(Icons.tune_outlined), selectedIcon: Icon(Icons.tune), label: 'Ajustes'),
        ],
      ),
    );
  }
}
