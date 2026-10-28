import 'package:flutter/material.dart';

import '../rotulos.dart';

/// Status com bolinha colorida e texto: a cor nunca carrega o significado sozinha.
class SeloStatus extends StatelessWidget {
  final String status;

  const SeloStatus(this.status, {super.key});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 9,
          height: 9,
          decoration: BoxDecoration(color: corDoStatus(status), shape: BoxShape.circle),
        ),
        const SizedBox(width: 6),
        Text(rotuloStatus(status)),
      ],
    );
  }
}

/// Marcador redondo do mapa com a sigla da classe (B ou C).
class MarcadorOcorrencia extends StatelessWidget {
  final String classe;
  final String status;

  const MarcadorOcorrencia({super.key, required this.classe, required this.status});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: corDoStatus(status),
        shape: BoxShape.circle,
        border: Border.all(color: Colors.white, width: 2),
        boxShadow: const [BoxShadow(color: Color(0x59000000), blurRadius: 4, offset: Offset(0, 1))],
      ),
      alignment: Alignment.center,
      child: Text(
        siglasClasse[classe] ?? '?',
        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 13),
      ),
    );
  }
}

/// Ponto azul da posicao do proprio cidadao.
class MarcadorUsuario extends StatelessWidget {
  const MarcadorUsuario({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF1A73E8),
        shape: BoxShape.circle,
        border: Border.all(color: Colors.white, width: 3),
        boxShadow: const [BoxShadow(color: Color(0x40000000), blurRadius: 6)],
      ),
    );
  }
}
