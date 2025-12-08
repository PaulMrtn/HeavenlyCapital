# `06-PHASE1-Bootstrapping-Threads`

## Objectif du Processus

Ce processus modélise l'étape critique de la **création des ressources de concurrence (Threads)** de notre architecture de trading.

Le but est de garantir que tous les **Pools d'I/O (Input/Output) spécialisés** — notamment le **Pool I/O CRITICAL** pour les ordres d'urgence et le **Pool I/O STANDARD** pour les ordres planifiés — sont instanciés, pré-alloués et prêts à l'emploi **avant l'ouverture du marché**.

## 💡 Importance de l'Instanciation Préalable

Le `Thread Manager` effectue ici un **bootstrapping** de ressources persistantes :

* **Réduction de la Latence :** En créant les threads en amont, nous éliminons l'**overhead** coûteux en temps de création de thread lors de l'exécution en temps réel. Les ordres critiques peuvent ainsi accéder instantanément à une ressource dédiée.
* **Isolation des Tâches :** L'initialisation de pools séparés garantit l'isolation physique de la charge de travail. Une tâche lente et massive (Bulk I/O) ne pourra jamais bloquer un `PoolWorker` du Pool I/O CRITICAL.
* **Configuration :** Le processus valide les paramètres de taille de pool (lus en base de données) et maintient les objets threads actifs pour toute la durée de la session de trading.

Le succès de cette séquence est une condition préalable pour le lancement de la phase d'Instanciation des Managers locaux et assure l'exécution optimale des ordres dans la **Phase In-Trade**.
