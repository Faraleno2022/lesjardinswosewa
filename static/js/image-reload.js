/**
 * Système de rechargement automatique des images
 * myschool
 */

(function() {
    'use strict';
    
    // Configuration
    const CONFIG = {
        // Intervalle de vérification en millisecondes (30 secondes)
        checkInterval: 30000,
        // Images à surveiller
        watchedImages: [
            'images/ecole.jpg',
            'images/carte1.jpg', 
            'images/carte2.jpg'
        ],
        // Seulement en mode développement
        enabled: window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost'
    };
    
    // Cache des versions d'images
    let imageVersions = {};
    
    /**
     * Obtient la version actuelle d'une image depuis le serveur
     */
    async function getImageVersion(imagePath) {
        try {
            const response = await fetch(`/static/${imagePath}`, {
                method: 'HEAD',
                cache: 'no-cache'
            });
            
            if (response.ok) {
                // Utiliser l'ETag ou Last-Modified comme version
                return response.headers.get('ETag') || 
                       response.headers.get('Last-Modified') || 
                       Date.now().toString();
            }
        } catch (error) {
            console.warn('Erreur lors de la vérification de l\'image:', imagePath, error);
        }
        
        return null;
    }
    
    /**
     * Recharge une image spécifique
     */
    function reloadImage(imagePath) {
        const images = document.querySelectorAll(`img[src*="${imagePath}"]`);
        
        images.forEach(img => {
            const currentSrc = img.src;
            const baseUrl = currentSrc.split('?')[0]; // Enlever les paramètres existants
            const newSrc = `${baseUrl}?v=${Date.now()}`;
            
            console.log(`🔄 Rechargement de l'image: ${imagePath}`);
            
            // Créer une nouvelle image pour précharger
            const newImg = new Image();
            newImg.onload = function() {
                // Remplacer l'image avec un effet de transition
                img.style.opacity = '0.5';
                setTimeout(() => {
                    img.src = newSrc;
                    img.style.opacity = '1';
                }, 100);
            };
            newImg.onerror = function() {
                console.warn(`❌ Erreur lors du rechargement de: ${imagePath}`);
            };
            newImg.src = newSrc;
        });
    }
    
    /**
     * Vérifie si les images ont été modifiées
     */
    async function checkForImageUpdates() {
        if (!CONFIG.enabled) return;
        
        for (const imagePath of CONFIG.watchedImages) {
            const currentVersion = await getImageVersion(imagePath);
            
            if (currentVersion) {
                const previousVersion = imageVersions[imagePath];
                
                if (previousVersion && previousVersion !== currentVersion) {
                    console.log(`📸 Image modifiée détectée: ${imagePath}`);
                    reloadImage(imagePath);
                }
                
                imageVersions[imagePath] = currentVersion;
            }
        }
    }
    
    /**
     * Initialise le système de surveillance
     */
    function initImageWatcher() {
        if (!CONFIG.enabled) {
            console.log('🔧 Surveillance des images désactivée (pas en développement)');
            return;
        }
        
        console.log('👁️ Surveillance automatique des images activée');
        
        // Vérification initiale
        checkForImageUpdates();
        
        // Vérifications périodiques
        setInterval(checkForImageUpdates, CONFIG.checkInterval);
        
        // Vérification lors du focus de la fenêtre
        window.addEventListener('focus', checkForImageUpdates);
        
        // Ajouter un bouton de rechargement manuel (seulement en dev)
        addManualReloadButton();
    }
    
    /**
     * Ajoute un bouton de rechargement manuel des images
     */
    function addManualReloadButton() {
        // Créer le bouton
        const button = document.createElement('button');
        button.innerHTML = '🔄 Recharger Images';
        button.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 9999;
            background: #007bff;
            color: white;
            border: none;
            padding: 10px 15px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 12px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            transition: all 0.3s ease;
        `;
        
        // Effets hover
        button.addEventListener('mouseenter', () => {
            button.style.background = '#0056b3';
            button.style.transform = 'scale(1.05)';
        });
        
        button.addEventListener('mouseleave', () => {
            button.style.background = '#007bff';
            button.style.transform = 'scale(1)';
        });
        
        // Action du bouton
        button.addEventListener('click', async () => {
            button.innerHTML = '⏳ Rechargement...';
            button.disabled = true;
            
            // Forcer le rechargement de toutes les images
            CONFIG.watchedImages.forEach(imagePath => {
                reloadImage(imagePath);
            });
            
            // Réinitialiser le cache des versions
            imageVersions = {};
            
            setTimeout(() => {
                button.innerHTML = '✅ Terminé!';
                setTimeout(() => {
                    button.innerHTML = '🔄 Recharger Images';
                    button.disabled = false;
                }, 1000);
            }, 500);
        });
        
        // Ajouter au DOM
        document.body.appendChild(button);
        
        // Masquer après 10 secondes, réapparaître au hover
        setTimeout(() => {
            button.style.opacity = '0.3';
            button.addEventListener('mouseenter', () => button.style.opacity = '1');
            button.addEventListener('mouseleave', () => button.style.opacity = '0.3');
        }, 10000);
    }
    
    /**
     * Fonction utilitaire pour forcer le rechargement d'une image spécifique
     * Disponible globalement pour les développeurs
     */
    window.reloadImage = function(imagePath) {
        reloadImage(imagePath);
    };
    
    /**
     * Fonction utilitaire pour recharger toutes les images
     */
    window.reloadAllImages = function() {
        CONFIG.watchedImages.forEach(imagePath => {
            reloadImage(imagePath);
        });
    };
    
    // Initialiser quand le DOM est prêt
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initImageWatcher);
    } else {
        initImageWatcher();
    }
    
})();
