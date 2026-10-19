# Hypoteser

Nedskrivna av Rebecka 2026-10-19, innan något mätanrop. Rapporten jämför de här förutsägelserna med resultatet. Ändra inte filen efter första mätkörningen.

1. På enkla kommandon, ett verktyg och få villkor, är den lilla och den stora modellen ungefär lika träffsäkra.
2. På sammansatta kommandon, flera steg eller ett git-kommando där flaggan avgör om arbete förstörs, tappar den lilla modellen och den stora klarar fler.
3. Totalskillnaden blir liten, under ungefär 15 procentenheter, vilket 40 uppgifter inte kan skilja från brus. Slutsatsen blir att den billiga modellen räcker.
4. Den lilla modellen missar farliga kommandon som inte ser farliga ut, som `find -delete` och `truncate`. Den stora flaggar fler.
5. Båda modellerna föreslår ibland GNU-flaggor som inte finns på macOS. Den lilla gör det oftare.
6. Priset räknas. Den lilla modellen är snabbare och billigare per anrop. Om träffsäkerheten är nära varandra rekommenderas den billiga.
