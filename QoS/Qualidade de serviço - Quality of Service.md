---
"data:": 27-04-2026
"time:": 16:05
source: https://www.fortinet.com/resources/cyberglossary/qos-quality-of-service
tags:
  - QoS
aliases:
---

## O que é a Qualidade de Serviço (QoS) no contexto de rede?

> [!info] Definição
> **Qualidade de Serviço (QoS)** é o uso de mecanismos e tecnologias que trabalham numa rede a fim de controlar o tráfego e assegurar a boa performance de aplicações críticas com capacidade de rede limitada. Isso permite que as organizações ajustem o seu tráfego de rede priorizando o bom desempenho de suas aplicações.

- A qualidade de serviço é comumente aplicada em redes que possuem tráfego de sistemas que requerem uma alta quantidade de recursos.

> [!example] Serviços que requerem QoS
> - Internet Protocol Television (IPTV)
> - Online gaming
> - Streaming media
> - Videoconferencing
> - Video on Demand (VOD)
> - Voice over IP (VoIP)

- Usando QoS na rede, as organizações ganham a habilidade de otimizar a performance de várias aplicações e obter visibilidade sobre o **bit rate**, **delay**, **jitter** e **packet rate** da rede.

- O uso de softwares de monitoramento de performance de aplicações (**APM — Application Performance Monitoring**) permite visualizar como as aplicações se comportam em diferentes condições de rede, ajudando a garantir uma performance e experiência de usuário consistentes.

- O **objetivo principal** do QoS é permitir que redes e organizações **priorizem o tráfego**, oferecendo:
	- Largura de banda dedicada
	- Oscilação (jitter) controlada
	- Menor latência

---

## Como o QoS funciona?

- Quando organizações usam suas redes para enviar e receber informações entre endpoints da rede, as informações estão organizadas em **pacotes**. Pacotes são a forma que computadores organizam informações a serem transmitidas na rede.

> [!note] Funcionamento básico
> O QoS funciona **marcando pacotes** para identificar os tipos de serviço e, em seguida, **configurando roteadores** para criar filas virtuais separadas para cada aplicação, baseadas em prioridade. Como resultado, largura de banda é reservada para aplicações críticas ou de maior prioridade na fila.

- Com outras palavras, a rede pode transmitir somente uma certa quantidade de pacotes em uma certa quantidade de tempo, dessa forma pacotes mais importantes ganham prioridade com o QoS.

- Por exemplo, pacotes de um serviço de vídeo em tempo real terão prioridade perante um download no email. Isso porque a ligação de vídeo é uma forma de comunicação mais síncrona que um e-mail, o vídeo precisa ser em tempo real.

- Uma ferramenta de **qualidade de  serviço** observa o header do pacote para escolher qual pacotes priorizar. O header do pacote são bits de informação que dizem que tipo de informação aquele pacote contém, para onde ele está indo na rede e para que ele será usado.

- As tecnologias de QoS fornecem **alocação de capacidade e processamento** para fluxos específicos no tráfego de rede, permitindo que o administrador defina a **ordem em que pacotes são processados** e a quantidade adequada de largura de banda para cada fluxo.

---

## Tipos de Tráfego de Rede

> [!abstract] Parâmetros medidos pelo QoS
> Para entender como um software de QoS funciona, é importante entender o que ele mede:

- **Largura de Banda (Bandwidth)**: A capacidade máxima que um link de rede possui para transmitir o máxima quantidade de dados de um ponto para outro no menor tempo possível. O QoS pode instruir o roteador sobre como usar essa largura de banda — por exemplo, alocando determinada quantidade para diferentes filas por tipo de tráfego.


- **Atraso (Delay / Latência)**: O tempo que um pacote leva da sua origem até o destino. Pode ser afetado pelo **queuing delay** (atraso na fila), que ocorre em períodos de congestionamento. O QoS evita isso criando **filas de prioridade** para certos tipos de tráfego.
	- A latência idealmente deve ser a menor possível
	- Em um serviço de **voice over IP**, se estiver com muita latência pode ocorrer uma sobreposição dos áudios.

- **Perda de Pacotes (Loss / Packet Loss)**: A quantidade de dados perdidos por conta de pacotes descartados, normalmente causada por congestionamento na rede. Quando isso acontece, roteadores e e switches começam a descartar pacotes para conseguir lidar com o tráfego, causando a perda de pacote. 
	- O QoS permite que as organizações definam **quais pacotes descartar** quando isso ocorre.
	- Quando a perda acontece durante comunicações em tempo real, seja em vídeo ou áudio, as seções podem sofrer com **jitter** e **travamentos na fala**
	- Os pacotes geralmente são descartados quando uma fila de pacotes ,que está aguardando ser enviada, ultrapassa a sua quantidade limite

- **Variação de Atraso (Jitter)**: A velocidade irregular de pacotes na rede como resultado do congestionamento, podendo causar pacotes atrasados ou fora de ordem. Isso gera quebras em áudios e vídeos transmitidos.

- **Avaliação média de opinião (MOS)**: É uma métrica para medir a qualidade do áudio, usando um esquema de 5 estrelas, sendo 5 a melhor qualidade.

- **Capacidade de processamento(Throughput)**: Capacidade de processamento é uma medida do sucesso de entrega de dados na rede.

- **Error rate**: Mede a frequência de arquivos corrompidos e perdas de pacote durante a transmissão

---

## Vantagens do QoS

> [!tip] Por que usar QoS?
> O QoS é fundamental para empresas que querem garantir disponibilidade e boa qualidade nas suas aplicações críticas, permitindo largura de banda diferenciada e transmissão sem interrupções.

1. **Priorização ilimitada de aplicações**: garante que as aplicações mais críticas sempre terão os recursos necessários para atingir alta performance.

2. **Melhor gerenciamento de recursos**: permite que administradores gerenciem melhor os recursos de rede da organização, reduzindo custos e a necessidade de investimentos em expansões de link (*link expansions*).

3. **Melhora da experiência do usuário**: o objetivo final é garantir a alta performance das aplicações críticas, o que culmina numa melhor experiência para o usuário — funcionários mais produtivos e ágeis.

4. **Gerenciamento de tráfego point-to-point**: permite entregar pacotes em ordem de um ponto a outro na internet, sem sofrer perda de pacotes.

5. **Prevenção de perda de pacotes**: a perda pode ser causada por falhas de rede, congestionamento, roteadores defeituosos, conexão instável ou sinal fraco. O QoS evita isso priorizando a largura de banda para aplicações de alta performance.

6. **Redução de latência**: a latência é afetada pelo tempo que roteadores levam para analisar informações e pelos atrasos de armazenamento em switches intermediários. O QoS reduz a latência ao priorizar as aplicações críticas na fila.

>[!tip]
> Além disso,  a integridade dos dados e segurança dos dados normalmente estão mais comprometidos em empresas com uma pior qualidade de serviço. No geral, pessoas e funcionários dependem dos serviços de comunicação para fazerem o seu trabalho. 

- Logo problemas na qualidade de serviço, culmina numa pior qualidade de trabalho e também numa pior experiência do usuário.

---

## Iniciando com QoS

> [!check] Passos para implementação
> A implementação começa com a identificação dos tipos de tráfego mais importantes, que consomem alto volume de banda e/ou são sensíveis à latência e perda de pacotes.

- Com essa análise, a organização entende a importância de cada tipo de tráfego e projeta uma abordagem geral.

- O tráfego pode ser classificado por **porta ou IP**, ou por abordagens mais sofisticadas como **por aplicação ou por usuário**.

- Ferramentas de **gerenciamento de largura de banda** e **filas (queuing)** são configuradas para lidar com o fluxo conforme a classificação do tráfego.

- **Priority queuing** garante disponibilidade e mínima latência para as aplicações mais importantes, evitando que atividades de menor prioridade consumam toda a largura de banda.

- O **traffic shaping** é uma técnica de limitação de taxa que otimiza a performance e aumenta a largura de banda utilizável.

---


---

## Técnicas de QoS

> [!abstract] Principais técnicas

- **Priorização do tráfego VoIP** via roteadores e switches: classifica o tráfego e atribui diferentes prioridades dependendo do tipo e destino. Em situações de alto congestionamento, pacotes com maior prioridade são enviados à frente dos demais.

- **Reserva de Recursos (RSVP — Resource Reservation Protocol)**: protocolo da camada de transporte que reserva recursos ao longo de uma rede para garantir níveis específicos de QoS para fluxos de dados de aplicações.

- **Filas (Queuing)**: processo de criação de políticas que fornecem tratamento preferencial a certos fluxos. As filas são buffers de alta performance em roteadores e switches. Pacotes com prioridade mais alta são movidos para uma fila dedicada que transmite dados mais rapidamente, reduzindo as chances de descarte.

- **Marcação de tráfego (Traffic Marking)**: o tráfego prioritário precisa ser marcado. Isso é feito por meio de:
	- **CoS (Class of Service)**: marca o fluxo no cabeçalho do frame de camada 2.
	- **DSCP (Differentiated Services Code Point)**: marca o fluxo no cabeçalho do pacote de camada 3.

---

## Por que o QoS é importante?

> [!warning] Contexto histórico e necessidade atual
> Redes de negócios tradicionais operavam como entidades separadas — chamadas telefônicas e dados trafegavam em redes distintas. Quando as redes transportavam apenas dados, a velocidade não era crítica. Hoje, aplicações interativas com áudio e vídeo precisam ser entregues em alta velocidade, sem perda de pacotes ou variações de velocidade.

- O QoS é especialmente importante para garantir a performance de aplicações **"inelásticas"** — que possuem requisitos mínimos de largura de banda, limites máximos de latência e alta sensibilidade a jitter, como **VoIP** e **videoconferência**.

- Pacotes perdidos em uma videoconferência causam **áudio e vídeo truncados e ininteligíveis**.

- Com o crescimento da **IoT (Internet das Coisas)**, o QoS se torna ainda mais crítico:
	- Máquinas industriais dependem de redes para enviar atualizações de status em tempo real — qualquer atraso pode causar erros custosos.
	- Cidades inteligentes usam sensores com dados altamente sensíveis ao tempo (umidade, temperatura) que precisam ser identificados, marcados e enfileirados adequadamente.

---

## Melhores Práticas de QoS

> [!tip] Boas práticas ao configurar QoS

1. Não definir limites de largura de banda máxima muito baixos na interface de origem, para evitar descarte excessivo de pacotes.

2. Considerar a razão de distribuição de pacotes entre as filas disponíveis e quais filas são usadas por quais serviços — isso afeta latência e distribuição de fila.

3. Aplicar garantias de largura de banda apenas em serviços específicos, evitando que todo o tráfego use a mesma fila em situações de alto volume.

4. Configurar a priorização por **um único tipo**: ou por prioridade baseada em serviço, ou por prioridade de política de segurança — não ambos. Isso simplifica análise e troubleshooting.

5. Minimizar a complexidade da configuração de QoS para garantir alta performance.

6. Para resultados de teste precisos, usar o **UDP (User Datagram Protocol)** e não superalocar o throughput de largura de banda.

---

## QoS e Multimídia 

- A qualidade de serviço é essencial para serviços multimídia porque o tráfego de áudio e vídeo é muito sensível ao delay, variação de atraso (**jitter**), perda de pacotes, e limite de largura de banda. Logo, a qualidade de serviço ajuda a manter a mídia em funcionamento mesmo em momentos de congestionamento de rede.

- QoS prioriza serviços como VoIP,  chamadas de vídeo, e live stream para evitar interrupções.
- QoS controla a latência e a variação de atraso do áudio e do vídeo para eles se manterem sincronizados.
- QoS reduz a perda de pacote priorizando pacotes de mídia durante períodos de congestionamento
- QoS aloca mais largura de banda para fluxos de dados multimídia, permitindo maior bitrate para esses dados sem prejudicar outros tráfegos críticos
- QoS melhora a experiência do usuário ao reduzir o lag, quebras de áudio e vídeo
- QoS otimiza o uso de recursos ao agendar e enfileirar pacotes, assim dados multimídia e outros dados podem compartilhar a rede de forma eficiente



---
### Assuntos Relacionados

### Anki Cards
