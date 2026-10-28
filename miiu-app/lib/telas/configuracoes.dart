import 'package:flutter/material.dart';

import '../servicos/api.dart';
import '../servicos/armazenamento.dart';
import '../servicos/geocerca.dart';
import '../servicos/push.dart';

class TelaConfiguracoes extends StatefulWidget {
  const TelaConfiguracoes({super.key});

  @override
  State<TelaConfiguracoes> createState() => _TelaConfiguracoesState();
}

class _TelaConfiguracoesState extends State<TelaConfiguracoes> {
  final TextEditingController _url = TextEditingController(text: Armazenamento.urlApi);
  String? _resultadoTeste;
  bool _testando = false;

  @override
  void dispose() {
    _url.dispose();
    super.dispose();
  }

  Future<void> _salvarETestar() async {
    FocusScope.of(context).unfocus();
    await Armazenamento.definirUrlApi(_url.text);
    _url.text = Armazenamento.urlApi;
    setState(() {
      _testando = true;
      _resultadoTeste = null;
    });
    String resultado;
    try {
      final saude = await Api.saude();
      final modelo = saude['modelo'] as Map<String, dynamic>?;
      final disponivel = modelo?['disponivel'] == true;
      resultado = 'Conectado. Banco: ${saude['banco']}. '
          'Modelo: ${disponivel ? modelo!['versao'] : 'indisponível'}. '
          'Push: ${saude['notificacoes']}.';
      await Api.registrarDispositivo(tokenFcm: Push.token);
    } on ErroApi catch (e) {
      resultado = 'Falhou: ${e.mensagem}';
    } catch (e) {
      resultado = 'Falhou: $e';
    }
    if (!mounted) return;
    setState(() {
      _testando = false;
      _resultadoTeste = resultado;
    });
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final geo = ServicoGeocerca.instancia;
    return Scaffold(
      appBar: AppBar(title: const Text('Ajustes')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Servidor', style: tema.textTheme.titleMedium),
          const SizedBox(height: 8),
          TextField(
            controller: _url,
            keyboardType: TextInputType.url,
            decoration: const InputDecoration(
              labelText: 'Endereço da API',
              helperText: 'Emulador: http://10.0.2.2:8000 · Celular: http://IP-DO-PC:8000',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: FilledButton.tonal(
              onPressed: _testando ? null : _salvarETestar,
              child: Text(_testando ? 'Testando…' : 'Salvar e testar conexão'),
            ),
          ),
          if (_resultadoTeste != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(_resultadoTeste!),
            ),
          const Divider(height: 32),
          Text('Alertas', style: tema.textTheme.titleMedium),
          ValueListenableBuilder<bool>(
            valueListenable: geo.ativo,
            builder: (context, ativo, _) => SwitchListTile(
              contentPadding: EdgeInsets.zero,
              value: ativo,
              title: const Text('Alertas de proximidade'),
              subtitle: const Text('Avisa quando você chega perto de um problema validado.'),
              onChanged: (ligar) async {
                if (ligar) {
                  final erro = await geo.ligar();
                  if (erro != null && context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(erro)));
                  }
                } else {
                  await geo.desligar();
                }
              },
            ),
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(Push.disponivel ? Icons.notifications_active_outlined : Icons.notifications_off_outlined),
            title: Text(Push.disponivel ? 'Notificações push ativas' : 'Notificações push não configuradas'),
            subtitle: Text(
              Push.disponivel
                  ? 'Os alertas chegam mesmo com o app fechado.'
                  : 'Os alertas aparecem com o app aberto. Para receber com o app fechado, '
                      'configure o Firebase (veja o README do projeto).',
            ),
          ),
          const Divider(height: 32),
          Text('Privacidade', style: tema.textTheme.titleMedium),
          const SizedBox(height: 8),
          const Text(
            'O MIIU não pede cadastro: este aparelho é identificado por um código aleatório. '
            'Sua localização é usada apenas para registrar onde está o problema e para '
            'verificar a proximidade de ocorrências; ela não é armazenada no servidor. '
            'Os metadados das fotos (como modelo do celular e GPS embutido) são removidos.',
          ),
          const SizedBox(height: 8),
          Text(
            'Código do aparelho: ${Armazenamento.deviceId.substring(0, 8)}…',
            style: tema.textTheme.bodySmall,
          ),
          const Divider(height: 32),
          Text(
            'MIIU · Monitoramento Inteligente de Infraestrutura Urbana\n'
            'Trabalho de Conclusão de Curso · Ciência da Computação · UESPI',
            style: tema.textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}
