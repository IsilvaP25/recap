import re

# Existing markers in Capitulo_1_Guion.txt: 01-13, 17-18, 21-24.

missing_14 = """
### PAGE_14

(Voz en off con un tono profundamente c’nico)

Observen esta lecci—n de humildad log’stica. Mientras la maga —probablemente otra unidad con un potencial desperdiciado— se queda boquiabierta, nuestro protagonista Ed despliega su verdadera arma: el conocimiento acumulado. No necesita pociones milagrosas ni hechizos prohibidos; solo un manual de instrucciones. La chica, con una capacidad de asombro que roza lo patŽtico, pregunta si esto es algœn tipo de "Almacenamiento Dimensional". (Pausa sarc‡stica) Ed, con la paciencia de quien ha corregido el mismo error en cien realidades distintas, responde con un simple "es similar". No es magia, es eficiencia. Es la diferencia entre un aventurero que conf’a en el destino y un estratega que ha indexado cada variable del sistema. "Lee esto", le dice, entreg‡ndole la soluci—n a problemas que ella ni siquiera sabía que ten’a. Bienvenidos a la verdadera escuela de la supervivencia.

[UPDATE_LORE]
- **Hobby de Ed:** Creaci—n y gesti—n de manuales de instrucciones tŽcnicos.
- **Nueva Habilidad Mencionada:** Almacenamiento Dimensional (o tŽcnica equivalente de compresi—n de datos).
"""

missing_15 = """
### PAGE_15

(Tono anal’tico y mordaz)

Miren esa cara. Es la expresi—n de alguien cuyo sistema operativo cerebral acaba de sufrir un error de segmentaci—n. La maga est‡ procesando la idea de que "leer" es una habilidad OP, mientras Ed ya est‡ tres pasos por delante calculando el costo de oportunidad de su ignorancia. "Si tienes este tipo de habilidad, entonces hay muchas formas de utilizarla", explica Ed con la frialdad de un consultor de gestión de recursos. Ella, por supuesto, reacciona gritando por quŽ no lo mencion— antes. Como si el conocimiento tŽcnico fuera algo que se debiera regalar a los mediocres por el simple hecho de existir. Ed no se molesta; para Žl, esto es solo una demostraci—n de c—mo la falta de una buena base de datos puede llevar al colapso de una unidad de combate. "En lugar de eso, deber’as leer esto", repite, insistiendo en que el verdadero poder reside en la documentaci—n, no en el grito desesperado.

[UPDATE_LORE]
- **Interacci—n Cr’tica:** Ed comienza a entrenar (o al menos a documentar) a la maga elfa.
- **Filosof’a:** El conocimiento documentado es superior a la fuerza bruta.
"""

missing_16 = """
### PAGE_16

(Voz en off con tono sombr’o y profundamente sarc‡stico)

Y por si quedaba alguna duda de quiŽn es el adulto en la habitaci—n, Ed vuelve a reunirse con su antiguo grupo, pero no para pedir perd—n, sino para realizar una entrega de activos tŽcnicos. "He reunido una lista de mŽtodos de entrenamiento eficientes", dice con una calma que debe estar d‡ndoles arcadas a esos "hŽroes" de pacotilla. Es como si un ingeniero de la NASA intentara explicarle a un cavernícola c—mo usar una palanca. Miren al l’der del equipo al fondo, con esa cara de confusi—n cr—nica. Pero lo mejor es la clŽriga —la unidad de apoyo m‡s 'inocente' del grupo— que se acerca con una duda existencial sobre una magia cuyo nombre ni siquiera conoce. "Umm... hay esta magia que se supone que debo aprender...". La respuesta de Ed es un simple "Oh, ya veo", con la resignaci—n de quien ya ha diagnosticado la falla de sistema y sabe que el parche ser‡ doloroso. Bienvenidos al servicio tŽcnico de la aventura, donde Ed es el œnico con el manual de usuario.

[UPDATE_LORE]
- **Actividad:** Ed entrega gu’as de optimizaci—n a su antiguo equipo (a pesar de la traici—n).
- **Rasgo de Ed:** Altruismo tŽcnico o simplemente incapacidad de ver procesos ineficientes sin intentar corregirlos.
"""

missing_19 = """
### PAGE_19

(Tono sombr’o y cargado de una calma absoluta)

Miren el nivel de desesperaci—n en el rostro del "HŽroe". "Estoy avergonzado de ped’rtelo de nuevo...". (Pausa burlona) ¿Escuchan eso? Es el sonido del colapso de un sistema que cre’a ser autosuficiente. Se han dado cuenta, demasiado tarde, de que sin la gesti—n de Ed, su 'Žlite' es solo un grupo de aficionados perdidos en un bosque. "Con nosotros... vuelve con nosotros", ruega con la dignidad de un mendigo. Pero Ed, con una firmeza que corta como un bistur’ tŽcnico, levanta las manos. "Lo siento, pero no puedo volver". No es rencor; es que Ed ya ha actualizado su zona de operaciones y ellos ya no son compatibles con su nueva arquitectura de poder. El l’der tartamudea, intenta dar excusas de que "no es as’", pero el daño sistŽmico ya es irreversible. Ed ya no pertenece a este equipo de mediocres; Žl ya est‡ procesando su propia transmigraci—n.

[UPDATE_LORE]
- **Conflicto:** El antiguo equipo intenta reclutar a Ed tras notar su incompetencia sin Žl.
- **Respuesta de Ed:** Rechazo absoluto; fin de la fase de soporte para el equipo A.
"""

missing_20 = """
### PAGE_20

(Voz en off con tono anal’tico y gŽlido)

Observen la fragmentaci—n emocional. Mientras el l’der intenta racionalizar por quŽ es "malo" haberlo desterrado y luego pedirle que vuelva, Ed ya ni siquiera los est‡ escuchando al nivel b‡sico. Para Žl, ellos son datos de una simulaci—n fallida. "No es conveniente desterrarte y luego pedirte que vuelvas ahora", admite el l’der con la sudoraci—n propia de un sistema al borde de la sobrecarga. Ed simplemente observa, con esa mirada que analiza vectores y flujos de mana mientras el pasado se desintegra. Han decidido purgar el cerebro del equipo y ahora descubren que el cuerpo no sabe c—mo caminar solo. El tiempo de las negociaciones ha terminado; la fase de auditor’a externa de Ed ha concluido y el proceso de transmigraci—n hacia la "Segunda Vuelta" es inminente. Adi—s, mediocres; disfruten de su inminente obsolescencia.

[UPDATE_LORE]
- **Resoluci—n:** Ed corta v’nculos finales con el grupo de mercenarios.
- **Estado:** Ed se prepara para el salto interdimensional / Cambio de mundo.
"""

def reassemble():
    with open("Capitulo_1_Guion.txt", "r", encoding="utf-8") as f:
        content = f.read()

    # Split by PAGE markers
    parts = re.split(r'(### PAGE_\d+)', content)
    
    pages = {}
    current_key = None
    for part in parts:
        if part.startswith("### PAGE_"):
            current_key = part.strip()
        elif current_key:
            pages[current_key] = pages.get(current_key, "") + part
    
    # Add missing
    pages["### PAGE_14"] = missing_14.replace("### PAGE_14", "")
    pages["### PAGE_15"] = missing_15.replace("### PAGE_15", "")
    pages["### PAGE_16"] = missing_16.replace("### PAGE_16", "")
    pages["### PAGE_19"] = missing_19.replace("### PAGE_19", "")
    pages["### PAGE_20"] = missing_20.replace("### PAGE_20", "")
    
    with open("Capitulo_1_Guion.txt", "w", encoding="utf-8") as f:
        for i in range(1, 25):
            key = f"### PAGE_{i:02d}"
            if key in pages:
                f.write(f"{key}\n{pages[key].strip()}\n\n")
            else:
                print(f"Warning: {key} still missing!")

reassemble()
