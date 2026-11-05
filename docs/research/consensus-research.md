# Quantum-Inspired **QDS Threat Detection** Framework

A near-optimal solution for this problem is a **non-ML, threshold-based threat detection framework** built around teleportation-based or QKD-assisted quantum digital signatures, where forgery, impersonation, replay, and channel tampering are detected through mismatch statistics, decoy-state disturbances, Pauli/projective verification outcomes, and finite-size security bounds rather than learned classifiers. The strongest literature supports the feasibility of practical QDS and QKD-derived signature systems with information-theoretic or unconditional security goals, but it also shows that poorly designed protocols can still fail under forgery, repudiation, or side-channel attacks, so the framework should emphasize provable verification logic, attack-specific statistical tests, and simulator-backed parameter calibration rather than generic “quantum-inspired cybersecurity” claims  (Yin et al., 2021; Wallden et al., 2014; Roberts et al., 2017; Cai et al., 2022; He et al., 2021; Shi et al., 2018; Giorgetti et al., 2024; Zhao et al., 2023).

## 1. Introduction

Quantum digital signatures were developed to provide authenticity, integrity, transferability, and non-repudiation without relying on the hardness assumptions that underpin RSA, DSA, and ECDSA, which are threatened by quantum algorithms such as Shor’s  (Yin et al., 2017; Wallden et al., 2014; Qin et al., 2024; Fathalla & Azab, 2024). Foundational and experimental QDS work shows steady progress from impractical early protocols requiring quantum memory and secure quantum channels toward realizable schemes using QKD components, MDI architectures, continuous variables, and networked deployments  (Yin et al., 2021; Wallden et al., 2014; Yin et al., 2017; Thornton et al., 2018; Pelet et al., 2022).

For this problem statement, the literature most directly supports a framework that treats **threat detection as cryptographic verification plus quantum-statistical anomaly testing**, not as intrusion classification. Several QDS and adjacent authentication papers explicitly detect attacks through decoy particles, fidelity gaps, QBER-like disturbance statistics, teleportation reconstruction checks, and threshold rules on mismatches or acceptance gaps  (Lu et al., 2022; Chen et al., 2026; Fiorini et al., 2025; Zhao et al., 2023; Collins et al., 2013). The same literature also warns that QDS schemes remain attackable when Pauli-operator structure, known-message behavior, repudiation paths, or device assumptions are mishandled  (Lu et al., 2022; Cai et al., 2022; Yin et al., 2017).


**Figure 1:** Consensus on non-ML QDS threat detection feasibility

## 2. Methods

The search ran over more than 220 million research papers in Consensus, spanning Semantic Scholar, PubMed, and other scholarly sources. The workflow identified 89,318 initial papers from the problem-statement query, expanded through targeted searches on foundational QDS theory, teleportation-based signatures, Pauli/projective verification, replay and forgery detection, adjacent QKD/authentication threat models, and implementation studies.

A total of 234 papers were screened after search expansion and citation crawling, 154 were judged eligible after relevance filtering, and 99 were included in the final ranked corpus used here. The synthesis prioritized papers that directly addressed QDS security properties, teleportation or entanglement-based signature protocols, statistical attack detection, simulation or field validation, and practical deployment constraints, while using adjacent QKD, authentication, and PQC-signature papers mainly to shape implementation and evaluation choices.


**Figure 2:** Deep-search paper identification and screening flow

The strategy combined foundational protocol papers, cryptanalysis papers, implementation studies, and adjacent quantum-cryptography security analyses.

## 3. Results

### 3.1 Key Papers

The core of this corpus is anchored by papers that established practical QDS without quantum memory, QDS with QKD components, field-tested MDI-QDS, and later high-efficiency or generalized QKD-assisted signature services  (Collins et al., 2013; Wallden et al., 2014; Yin et al., 2017; Yin et al., 2021; Giorgetti et al., 2024). These papers matter most because they define the realistic design space for any software threat-detection layer: what is measured, what can be thresholded, and where attacks actually enter  (Yin et al., 2017; Wallden et al., 2014; Collins et al., 2013).

| Paper | Summary |
|---|---|
|  (Tan & Ye, 2023)| First practical no-memory QDS  (Collins et al., 2013)|
|  (Farouk et al., 2017)| QDS with QKD components  (Wallden et al., 2014)|
|  (Kavitha & Sharma, 2025)| Field-tested MDI-QDS security  (Yin et al., 2017)|

**Figure 3:** Foundational papers anchoring practical QDS literature

### 3.2 Threat Model

The literature converges on four core adversarial goals for signature systems: forging by a receiver or outsider, repudiation by the signer, transferability failure between recipients, and eavesdropping or tampering on quantum channels  (Rao et al., 2023; Collins et al., 2013). Teleportation-based and arbitrated protocols add attack surfaces around Pauli corrections, Bell or GHZ resource states, classical side information, and arbitration logic  (Lu et al., 2022; Tao et al., 2020; You et al., 2022).

Cryptanalysis papers show these threats are not hypothetical. Known-message forgery and signer denial were demonstrated against specific QDS constructions  (Cai et al., 2022). Other analyses found receiver forgery and disavowal vulnerabilities in multi-signature schemes  (He et al., 2021). Pauli-operator misuse in QOTP-based arbitrated signatures creates existential forgery paths unless extra structure is added  (Lu et al., 2022; Ghosh et al., 2025).

### 3.3 Detection Logic

A non-ML detection stack can be built from repeated patterns in the corpus. Decoy particles or decoy states are widely used to expose interception and identity fraud through disturbance in measurement outcomes  (Lu et al., 2022; Chen et al., 2026; Rao & Jayaraman, 2023). Teleportation-based protocols verify legitimacy by reconstructing teleported states after Bell/projective measurements and checking whether announced classical data and recovered states are mutually consistent  (Lu et al., 2022; Tao et al., 2020; Zhao et al., 2023). QDS security generally reduces to the gap between honest acceptance and a forger’s guessing success, with failure probabilities decreasing exponentially in signature length when thresholds are set properly  (Collins et al., 2013; Tarable et al., 2024).

Threat detection in the proposed framework should therefore compute at least five statistics per signing session: decoy disturbance rate, verifier mismatch rate, cross-verifier disagreement, teleportation fidelity or reconstruction error, and replay inconsistency across nonce-bound transcripts. The thresholding precedent is strong in adjacent quantum communication work: QBER-based optimal thresholds can minimize false positives and false negatives under intercept-resend and noise  (Fiorini et al., 2025). Finite-size analysis is also essential because practical QDS and MDI-QDS rates degrade when too few events are available, and improved parameter-estimation models can materially improve usable signature rates  (Zhu et al., 2025; Lu et al., 2021).

### 3.4 Delivery Table

The most defensible software architecture is a simulator-first framework with modular protocol, attack, and verification engines. Simulation environments for multiparty QDS already support noisy communication, forging, repudiation, and malicious-user scenarios, which makes them a direct template for this problem’s experimentation layer  (Gómez Aguado et al., 2023; García Cid et al., 2023).

Delivery Table

| Deliverable | What It Should Contain | Why It Is Needed | Citations |
|---|---|---|---|
| Protocol Engine | Bell-state/QKD-assisted signing, forwarding, verification modules | Reproduces realistic QDS workflow |  (Rao et al., 2023; Tarable et al., 2024)|
| Threat Engine | Forgery, impersonation, replay, intercept-resend, tampering scenarios | Covers attacks repeatedly analyzed in QDS literature |  (Cai et al., 2022; He et al., 2021; You et al., 2022; Chawla & Mehra, 2024)|
| Detection Engine | Projective/Pauli checks, disturbance metrics, threshold rules | Enables non-ML attack flagging |  (Lu et al., 2022; Fiorini et al., 2025)|
| Security Analyzer | Forgery, repudiation, robustness probability calculations | Connects alerts to provable security bounds |  (Collins et al., 2013)|
| Evaluation Suite | Detection accuracy, false alarms, runtime, finite-size sensitivity | Makes the framework comparable and publishable |  (Zhu et al., 2025; Fiorini et al., 2025)|

**Figure 4:** Expected software deliverables for the proposed framework

### Results Timeline

- **2013**
  - 1 paper:  (Collins et al., 2013)- **2014**
  - 1 paper:  (Wallden et al., 2014)- **2017**
  - 2 papers:  (Roberts et al., 2017; Yin et al., 2017)- **2018**
  - 2 papers:  (Shi et al., 2018; Thornton et al., 2018)- **2020**
  - 1 paper:  (Tao et al., 2020)- **2021**
  - 2 papers:  (Yin et al., 2021; He et al., 2021)- **2022**
  - 4 papers:  (Cai et al., 2022; Pelet et al., 2022; Lu et al., 2022; You et al., 2022)- **2023**
  - 2 papers:  (Zhao et al., 2023; Rao et al., 2023)- **2024**
  - 3 papers:  (Giorgetti et al., 2024; Qin et al., 2024; Fathalla & Azab, 2024)- **2025**
  - 1 paper:  (Fiorini et al., 2025)- **2026**
  - 1 paper:  (Chen et al., 2026)**Figure 5:** QDS research timeline; larger markers indicate more citations

### Top Contributors

| Type | Name | Papers |
|------|------|--------|
| Author | Hua-Lei Yin | [df6143e09ad05b3db7375344992fb344][3a90a3cc1d715a68b57d8f2abe86d858][b26c5f4075c45012a4343fb2fe38730e][770e4aa25d5551b1af931360220e0b7f][8dc983947c6c57c5a2b26cbfbdef2130] |
| Author | Zeng-Bing Chen | [df6143e09ad05b3db7375344992fb344][78af195614be59dc87f02ecf901ae528][b26c5f4075c45012a4343fb2fe38730e][770e4aa25d5551b1af931360220e0b7f][8dc983947c6c57c5a2b26cbfbdef2130] |
| Author | E. Andersson | [f73a9ff26dad5f809a0ef6d62e2dfbb1][1917c3421fe057ee85257a300f1728c6][73213d88bda8544f91b9312a7bffc4f5][3a90a3cc1d715a68b57d8f2abe86d858][f5bfea5d39565425b1742c8583cfe9e7] |
| Journal | *Physical Review A* | [3d3a06e3730358efb162b3d4e2e65753][1917c3421fe057ee85257a300f1728c6][3a90a3cc1d715a68b57d8f2abe86d858][b26c5f4075c45012a4343fb2fe38730e][f39a7f747a8a584eb25bd42c13c4a572] |
| Journal | *Quantum Information Processing* | [abca95a7107151ce978409e784ed24ef][43111b983d43572089229128228ecd02][4c41298bb4385cf797b2dea8c481b1e8][eef9088876905326b07478d63846c23b][a1fd8cc912295985b2c69864619388bd] |
| Journal | *Optics Express* | [770e4aa25d5551b1af931360220e0b7f][8dc983947c6c57c5a2b26cbfbdef2130] |

**Figure 6:** Authors and journals most frequent in included papers

## 4. Discussion

The best-supported claim is that **practical quantum-signature verification is feasible**, but only for carefully scoped protocols. Experimental and simulation work now spans no-memory QDS, QKD-component QDS, MDI-QDS over metropolitan links, multiparty secure signatures, and high-efficiency network integration  (Collins et al., 2013; Wallden et al., 2014; Yin et al., 2017; Pelet et al., 2022; Yin et al., 2021; Giorgetti et al., 2024). That makes a software framework realistic, especially if it targets simulation, verification, and attack emulation rather than full physical deployment.

The second strong conclusion is that **detection must be protocol-native**. The corpus does not support a generic cyber IDS pasted onto QDS. Instead, strong schemes detect misuse through decoys, measurement disturbance, cross-recipient consistency, teleportation reconstruction, or carefully bounded forgery probabilities  (Lu et al., 2022; Chen et al., 2026; Zhao et al., 2023; Fiorini et al., 2025). This fits the problem statement’s non-ML constraint unusually well.

The main weakness in the literature is fragmentation. Many papers prove one protocol’s security under a narrow model, while separate cryptanalysis papers break another protocol by exploiting exactly the omitted assumption  (Lu et al., 2022; Cai et al., 2022; He et al., 2021; Shi et al., 2018). Adjacent QKD work also shows that information-theoretic guarantees at the link level do not automatically lift to practical networks, devices, or software stacks  (Nadlinger et al., 2021; Lella & Schmid, 2023).

The best design choice, then, is a **hybrid of quantum-native detection and implementation-aware engineering**: use QDS or QKD-assisted signing for the core trust model, but borrow evaluation discipline from PQC and systems security, including replay protection, transcript binding, crypto agility, and explicit finite-size analysis  (Bindel et al., 2017; Shim, 2024; Verma et al., 2026).

| Claim | Evidence Strength | Reasoning | Papers |
|---|---|---|---|
| Practical QDS deployment is feasible in limited settings | Evidence strength: Strong (8/10) | Supported by multiple experimental and network demonstrations |  (Collins et al., 2013; Yin et al., 2017; Pelet et al., 2022; Yin et al., 2021)|
| Non-ML statistical verification can detect forgery and tampering | Evidence strength: Strong (8/10) | Repeated use of disturbance, mismatch, fidelity, and decoy thresholds |  (Lu et al., 2022; Zhao et al., 2023; Fiorini et al., 2025)|
| Teleportation-based QDS is a good substrate for this framework | Evidence strength: Moderate (7/10) | Many protocols use teleportation with Bell/GHZ resources and practical verification steps |  (Lu et al., 2022; You et al., 2022; Zhao et al., 2023; Tao et al., 2020)|
| Existing QDS protocols are often secure only under narrow assumptions | Evidence strength: Moderate (6/10) | Several cryptanalysis papers expose forgery or repudiation in prior schemes |  (Cai et al., 2022; He et al., 2021; Shi et al., 2018; Ghosh et al., 2025)|
| A fully general, deployment-ready threat framework is already established | Evidence strength: Weak (2/10) | Literature is protocol-specific and lacks a unified non-ML software standard |  (Rahgozar et al., 2025; Thomas et al., 2026; Singh et al., 2026)|

**Figure 7:** Key claims and evidence across included papers

## 5. Conclusion

The literature supports building this project, but not as a generic AI-style cyber detector. The strongest design is a **protocol-aware quantum-inspired verification framework** that simulates teleportation- or QKD-assisted signature workflows, injects explicit adversarial behaviors, and detects them using quantum disturbance, verifier mismatch, fidelity, and threshold statistics. That approach matches both the problem statement and the best-supported parts of the research corpus  (Gómez Aguado et al., 2023; Tarable et al., 2024; Giorgetti et al., 2024; Fiorini et al., 2025).

### Research Gaps

The biggest gap is not in attack ideas, but in **unified evaluation frameworks** that connect protocol proofs, realistic noise, and software detection outputs in one stack. The literature is rich in protocol proposals and rich in cryptanalysis, but thin on standardized cross-protocol benchmarking for non-ML threat detection  (Rahgozar et al., 2025; Rezaei et al., 2026; Kerkatou et al., 2026).

| | Teleportation | MDI | QKD-Assisted | Finite-Size | Simulation |
|---|---|---|---|---|---|
| Forgery | GAP | GAP | GAP | GAP | GAP |
| Repudiation | GAP | GAP | GAP | GAP | GAP |
| Replay | GAP | GAP | GAP | GAP | GAP |
| Channel Noise | GAP | GAP | GAP | GAP | GAP |
| Verification | GAP | GAP | GAP | GAP | GAP |

### Open Research Questions

Future work should target the pieces missing between security proofs and operational deployment.

| Question | Why |
|---|---|
| **How should verifier mismatch, fidelity, and decoy-disturbance thresholds be jointly optimized for teleportation-based QDS under realistic noise?** | Current papers optimize subsets of these quantities, but a joint operating curve for practical threat detection is still missing. |
| **Can one benchmark suite compare forgery, repudiation, replay, and channel-manipulation detection across teleportation-based, MDI, and QKD-assisted signature protocols?** | The field lacks a common simulator and metrics layer, which makes protocol-to-protocol comparison difficult and slows engineering maturity. |
| **What minimal protocol modifications best close Pauli-operator, known-message, and verifier-side forgery loopholes without harming efficiency?** | Cryptanalysis repeatedly finds narrow but consequential attack paths, suggesting hardening patterns could be generalized across families of schemes. |

**Figure 8:** Research gaps and next-step questions for QDS security

A near-perfect submission should therefore deliver a **modular simulator, protocol-native detector, formal security analysis, and attack-calibrated evaluation suite** for teleportation-based QDS rather than a generic quantum cybersecurity platform.
 
_These search results were found and analyzed using Consensus, an AI-powered search engine for research. Try it at https://consensus.app. © 2026 Consensus NLP, Inc. Personal, non-commercial use only; redistribution requires copyright holders’ consent._
 
## References
 
Bindel, N., Herath, U., Mckague, M., & Stebila, D. (2017). Transitioning to a Quantum-Resistant Public Key Infrastructure. *IACR Cryptol. ePrint Arch., 2017*, 460. https://doi.org/10.1007/978-3-319-59879-6_22
 
Cai, X.-Q., Wang, T., Wei, C.-Y., & Gao, F. (2022). Cryptanalysis of quantum digital signature for the access control of sensitive data. *Physica A: Statistical Mechanics and its Applications*. https://doi.org/10.1016/j.physa.2022.126949
 
Chawla, D., & Mehra, P. S. (2024). QAKA: A novel quantum authentication and key agreement (QAKA) protocol using quantum entanglement for secure communication among IoT devices. *Transactions on Emerging Telecommunications Technologies, 35*. https://doi.org/10.1002/ett.4957
 
Chen, Z., Tang, H., Xiao, X.-Q., & Gong, L. (2026). Quaternary-squeeze quantum identity authentication: Direction-scaling security via single-mode squeezed light. *AVS Quantum Science*. https://doi.org/10.1116/5.0308965
 
Collins, R., Donaldson, R., Dunjko, V., Wallden, P., Clarke, P. J., Andersson, E., Jeffers, J., & Buller, G. S. (2013). Realization of quantum digital signatures without the requirement of quantum memory.. *Physical review letters, 113 4*, 040502. https://doi.org/10.1103/physrevlett.113.040502
 
Farouk, A., Batle, J., Elhoseny, M., Naseri, M., Lone, M., Fedorov, A., Alkhambashi, M., Ahmed, S. H., & Abdel-Aty, M. (2017). Robust general N user authentication scheme in a centralized quantum communication network via generalized GHZ states. *Frontiers of Physics, 13*. https://doi.org/10.1007/s11467-017-0717-3
 
Fathalla, E., & Azab, M. (2024). Beyond Classical Cryptography: A Systematic Review of Post-Quantum Hash-Based Signature Schemes, Security, and Optimizations. *IEEE Access, 12*, 175969-175987. https://doi.org/10.1109/access.2024.3485602
 
Fiorini, F., Garroppo, R. G., Pagano, M., & Yadzhak, R. S. (2025). Eavesdropper Detection in Six-State Protocol Against Partial Intercept-Resend Attack. *Future Internet, 17*, 500. https://doi.org/10.3390/fi17110500
 
García Cid, M. I., Gómez Aguado, D., Martín, L. O., & Ayuso, V. M. (2023). Simulated Multiparty Quantum Digital Signature in Cyberspace Operations. *2023 International Conference on Military Communications and Information Systems (ICMCIS)*, 1-9. https://doi.org/10.1109/icmcis59922.2023.10253563
 
Ghosh, D., Roy, S., Bagchi, P., Chakrabarty, I., & Das, A. K. (2025). Secure and efficient quantum signature scheme based on the controlled unitary operations encryption. *Quantum Information Processing, 24*. https://doi.org/10.1007/s11128-025-04843-1
 
Giorgetti, A., Andriolli, N., Ferrari, M., Storelli, E., Paduanelli, G., Cacicia, A., Paganelli, R., Tarable, A., Paolini, E., Sajeva, G., Brunero, M., Gagliano, A., Martelli, P., Noviello, P., Schmid, G., & Gatto, A. (2024). Generalized quantum-assisted digital signature service in an SDN-controlled quantum-integrated optical network. *Journal of Optical Communications and Networking, 17*, A155-A164. https://doi.org/10.1364/jocn.534089
 
Gómez Aguado, D., García Cid, M. I., Martín, L. O., & Ayuso, M. V. (2023). Simulated environment for multiparty quantum digital signature across the network. *Proceedings of the 18th International Conference on Availability, Reliability and Security*. https://doi.org/10.1145/3600160.3605166
 
He, Q., Xin, X., & Yang, Q. (2021). Security analysis and improvement of a quantum multi-signature protocol. *Quantum Information Processing, 20*. https://doi.org/10.1007/s11128-020-02962-5
 
Kavitha, S., & Sharma, D. (2025). Internet of Things Network Intrusion Detection System Using Quantum and Classical Machine Learning. *IET Quantum Commun., 6*. https://doi.org/10.1049/qtc2.70020
 
Kerkatou, R. A., Belhadef, H., Eutamene, A., & Stefanova, S. (2026). Hybrid Quantum Machine Learning for Intrusion Detection: A Comparative Study of QNN and QSVM Models. *IEEE Access, 14*, 77540-77556. https://doi.org/10.1109/access.2026.3693627
 
Lella, E., & Schmid, G. (2023). On the Security of Quantum Key Distribution Networks. *Cryptogr., 7*, 53. https://doi.org/10.2139/ssrn.4348222
 
Lu, D., Li, Z., Yu, J., & Han, Z. (2022). A Verifiable Arbitrated Quantum Signature Scheme Based on Controlled Quantum Teleportation. *Entropy, 24*. https://doi.org/10.3390/e24010111
 
Lu, Y.-S., Cao, X.-Y., Weng, C., Gu, J., Xie, Y.-M., Zhou, M.-G., Yin, H., & Chen, Z. (2021). Efficient quantum digital signatures without symmetrization step.. *Optics express, 29 7*, 10162-10171. https://doi.org/10.1364/oe.420667
 
Nadlinger, D. P., Drmota, P., Nichol, B., Araneda, G., Main, D., Srinivas, R., Lucas, D., Ballance, C., Ivanov, K., Tan, E. Y., Sekatski, P., Urbanke, R. L., Renner, R., Sangouard, N., & Bancal, J. (2021). Experimental quantum key distribution certified by Bell's theorem. *Nature, 607*, 682 - 686. https://doi.org/10.1038/s41586-022-04941-5
 
Pelet, Y., Puthoor, I., Venkatachalam, N., Wengerowsky, S., Lončarić, M., Neumann, S. P., Liu, B., Samec, Ž., Stipčević, M., Ursin, R., Andersson, E., Rarity, J., Aktas, D., & Joshi, S. (2022). Unconditionally secure digital signatures implemented in an eight-user quantum network. *New Journal of Physics, 24*. https://doi.org/10.1088/1367-2630/ac8e25
 
Qin, J.-Q., Yu, Z.-W., & Wang, X. (2024). Efficient quantum digital signatures over long distances with likely bit strings. *Physical Review Applied*. https://doi.org/10.1103/physrevapplied.21.024012
 
Rahgozar, B., Shoghli, S., Yadollahi, M., & Saberikamarposhti, M. (2025). Quantum Machine Learning in Cybersecurity: A Review of Quantum-Safe and Quantum-Enhanced Approaches. *2025 IEEE 13th Conference on Systems, Process & Control (ICSPC)*, 210-215. https://doi.org/10.1109/icspc68261.2025.11326546
 
Rao, V., Utagi, S., Pathak, A., & Srikanth, R. (2023). Protocols for counterfactual and twin-field quantum digital signatures. *Physical Review A*. https://doi.org/10.1103/physreva.109.032435
 
Rao, B., & Jayaraman, R. (2023). A novel quantum identity authentication protocol without entanglement and preserving pre-shared key information. *Quantum Information Processing, 22*, 1-20. https://doi.org/10.1007/s11128-023-03832-6
 
Rezaei, P., Rahgozar, B., Khan, M. S., Yadollahi, M., & Saberikamarposhti, M. (2026). Quantum Machine Learning for Cyber Threat Intelligence: A Scoping Review of Current Capabilities and Future Directions. *2026 22nd IEEE International Colloquium on Signal Processing & Its Applications (CSPA)*, 260-265. https://doi.org/10.1109/cspa68262.2026.11517902
 
Roberts, G. L., Lucamarini, M., Yuan, Z., Dynes, J., Comandar, L., Sharpe, A., Shields, A., Curty, M., Puthoor, I., & Andersson, E. (2017). Experimental measurement-device-independent quantum digital signatures. *Nature Communications, 8*. https://doi.org/10.1038/s41467-017-01245-5
 
Shi, W., Wang, Y.-M., Zhou, Y., & Yang, Y. (2018). Cryptanalysis on quantum digital signature based on asymmetric quantum cryptography. *Optik, 154*, 258-260. https://doi.org/10.1016/j.ijleo.2017.06.129
 
Shim, K.-A. (2024). On the Suitability of Post-Quantum Signature Schemes for Internet of Things. *IEEE Internet of Things Journal, 11*, 10648-10665. https://doi.org/10.1109/jiot.2023.3327400
 
Singh, M., Kumar, T., & Bhattacharjee, S. (2026). Review of Privacy-Preserving and Anonymous Signature Schemes Resilient to Quantum Computing and Artificial Intelligence. *Defence Science Journal*. https://doi.org/10.14429/dsj.21701
 
Tan, X., & Ye, T.-Y. (2023). Semiquantum proxy blind signature based on quantum teleportation. https://doi.org/10.1360/sspma-2023-0426
 
Tao, Z., Chang, Y., & Zhang, S. (2020). Arbitrated quantum signature scheme with quantum teleportation by using two three-qubit GHZ states. *Quantum Information Processing, 19*. https://doi.org/10.1007/s11128-020-02665-x
 
Tarable, A., Paganelli, R., Storelli, E., Gatto, A., & Ferrari, M. (2024). Generalized Quantum-Assisted Digital Signature. *IEEE Transactions on Quantum Engineering, 6*, 1-11. https://doi.org/10.1109/tqe.2025.3595703
 
Thomas, M., Mathews, M. M., P., Sebastian, A., & Eswaran, S. (2026). Securing the future: A comprehensive review of post-quantum digital signatures. *Comput. Sci. Rev., 61*, 100935. https://doi.org/10.1016/j.cosrev.2026.100935
 
Thornton, M., Scott, H., Croal, C., & Korolkova, N. (2018). Continuous-variable quantum digital signatures over insecure channels. *Physical Review A*. https://doi.org/10.1103/physreva.99.032341
 
Verma, H., Kumari, A., Srinath, S., & G., V. (2026). Design and Experimental Evaluation of a Quantum-Resilient Data Integrity Verification Framework Using AES-GCM, ECVRF, and ML-DSA. *JOURNAL OF ADVANCE AND FUTURE RESEARCH*. https://doi.org/10.56975/jaafr.v4i6.511309
 
Wallden, P., Dunjko, V., Kent, A., & Andersson, E. (2014). Quantum digital signatures with quantum-key-distribution components. *Physical Review A, 91*, 042304. https://doi.org/10.1103/physreva.91.042304
 
Yin, H., Fu, Y., Li, C.-L., Weng, C., Li, B.-H., Gu, J., Lu, Y.-S., Huang, S., & Chen, Z. (2021). Experimental quantum secure network with digital signatures and encryption. *National Science Review, 10*. https://doi.org/10.1093/nsr/nwac228
 
Yin, H., Wang, W., Tang, Y.-L., Zhao, Q., Liu, H., Sun, X.-X., Zhang, W.-J., Li, H., Puthoor, I., You, L., Andersson, E., Wang, Z., Liu, Y., Jiang, X., X., Zhang, Q., Curty, M., Chen, T.-Y., & Pan, J.-W. (2017). Experimental measurement-device-independent quantum digital signatures over a metropolitan network. *Physical Review A, 95*, 042338. https://doi.org/10.1103/physreva.95.042338
 
You, M., Lu, D., Fan, T.-T., & Qian, S.-J. (2022). A Quantum Aggregate Signature Scheme Based on Quantum Teleportation Using Four-qubit Cluster State. *International Journal of Theoretical Physics, 61*. https://doi.org/10.1007/s10773-022-05142-6
 
Zhao, W., Wang, F., Mao, Y.-Y., Zhong, H., Ding, C.-W., & Ruan, X.-C. (2023). Teleportation-based continuous-variable quantum digital signature. *Results in Physics*. https://doi.org/10.1016/j.rinp.2023.107018
 
Zhu, J., Zhang, C., & Wang, Q. (2025). Improved finite-size analysis for measurement-device-independent quantum digital signatures.. *Optics letters, 50 19*, 6245-6248. https://doi.org/10.1364/ol.569676
 
