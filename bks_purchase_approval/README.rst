================================
BKS Circuit validation DA / BDC
================================

Ce module configure le circuit de validation des **demandes d'achat (DA)**
et des **bons de commande (BDC)** à partir de
``purchase_request_tier_validation`` et ``purchase_tier_validation``.

Seuils (devise société, TTC pour le BDC)
========================================

* Palier 1 : montant <= 40 000 (40 KDH)
* Palier 2 : 40 000 < montant <= 700 000 (700 KDH)
* Palier 3 : montant > 700 000

Circuit DA (identique quel que soit le montant)
===============================================

1. Établissement : Ordonnateur (création du document)
2. Signature : Ordonnateur
3. Signature : Co-ordonnateur
4. Validation : Responsable Achats

Circuit BDC
===========

1. Établissement : Acheteur (création du document)
2. 1ère signature : Responsable Achats
3. 2ème signature : Co-ordonnateur
4. 3ème signature :

   * palier 1 : aucune
   * palier 2 : Directeur du Pôle
   * palier 3 : Président

Configuration
=============

1. Installer **Purchase Request Tier Validation**, **Purchase Tier Validation**,
   puis **BKS Circuit validation DA / BDC**.
2. Aller dans *Paramètres > Utilisateurs* et affecter les groupes :

   * Ordonnateur
   * Co-ordonnateur
   * Acheteur
   * Responsable Achats
   * Directeur du Pôle
   * Président

3. Les définitions de niveaux sont dans
   *Paramètres > Technique > Validations par niveaux > Définition de niveau*.

Utilisation
===========

1. Créer la DA, puis **Demander la validation**.
2. Chaque signataire valide à son tour.
3. Une fois toutes les revues acceptées, **Confirmer** la DA.
4. L'acheteur crée le BDC, puis **Demander la validation**.
5. Confirmer le BDC après les signatures requises selon le montant.
