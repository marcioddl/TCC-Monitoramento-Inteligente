// Textos exibidos ao cidadao e funcoes de formatacao (sem dependencias de
// pacotes, para poderem ser testadas isoladamente).

import 'package:flutter/material.dart';

const Map<String, String> rotulosClasse = {
  'buraco': 'Buraco na via',
  'calcada_danificada': 'Calçada danificada',
};

const Map<String, String> siglasClasse = {
  'buraco': 'B',
  'calcada_danificada': 'C',
};

const Map<String, String> rotulosStatus = {
  'recebida': 'Recebida',
  'classificada': 'Classificada automaticamente',
  'em_triagem': 'Em análise',
  'validada': 'Validada',
  'em_atendimento': 'Em atendimento',
  'resolvida': 'Resolvida',
  'rejeitada': 'Não procede',
};

const Map<String, String> explicacoesStatus = {
  'recebida': 'O reporte chegou ao sistema.',
  'classificada': 'A foto foi classificada pelo modelo e aguarda a confirmação da equipe de gestão.',
  'em_triagem': 'A equipe de gestão vai analisar a foto antes de validar.',
  'validada': 'Problema confirmado. Quem passar por perto recebe um alerta.',
  'em_atendimento': 'A equipe responsável está trabalhando no local.',
  'resolvida': 'O problema foi resolvido. Obrigado por colaborar!',
  'rejeitada': 'A equipe de gestão concluiu que o reporte não procede.',
};

// Mesmo agrupamento e cores do painel de gestao
const Color corAguardando = Color(0xFFEB6834);
const Color corAtiva = Color(0xFF2A78D6);
const Color corEncerrada = Color(0xFF898781);

String rotuloClasse(String? classe) => rotulosClasse[classe] ?? (classe ?? '–');

String rotuloStatus(String status) => rotulosStatus[status] ?? status;

Color corDoStatus(String status) {
  switch (status) {
    case 'validada':
    case 'em_atendimento':
      return corAtiva;
    case 'resolvida':
    case 'rejeitada':
      return corEncerrada;
    default:
      return corAguardando;
  }
}

String _doisDigitos(int n) => n.toString().padLeft(2, '0');

String formatarData(DateTime data) {
  final l = data.toLocal();
  return '${_doisDigitos(l.day)}/${_doisDigitos(l.month)}/${l.year} '
      '${_doisDigitos(l.hour)}:${_doisDigitos(l.minute)}';
}

String formatarDistancia(double metros) {
  if (metros < 1000) return '${metros.round()} m';
  return '${(metros / 1000).toStringAsFixed(1).replaceAll('.', ',')} km';
}

String formatarPorcentagem(double? valor) =>
    valor == null ? '–' : '${(valor * 100).round()}%';

String motivoIgnorada(String? motivo) {
  switch (motivo) {
    case 'precisao_gps_insuficiente':
      return 'Sinal de GPS fraco: aguardando uma localização mais precisa.';
    case 'notificacoes_desabilitadas':
      return 'Alertas desativados para este aparelho.';
    default:
      return 'Verificação não realizada.';
  }
}

/// Aceita o protocolo digitado com minusculas e espacos.
String normalizarProtocolo(String texto) {
  final limpo = texto.trim().toUpperCase().replaceAll(RegExp(r'[\s_\-]+'), '');
  final semPrefixo = limpo.startsWith('MIIU') ? limpo.substring(4) : limpo;
  if (semPrefixo.length != 10) return texto.trim().toUpperCase();
  final ano = semPrefixo.substring(0, 4);
  final sufixo = semPrefixo
      .substring(4)
      .replaceAll('O', '0')
      .replaceAll('I', '1')
      .replaceAll('L', '1');
  return 'MIIU-$ano-$sufixo';
}
