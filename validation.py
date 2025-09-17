"""
Validation module for the Pokemon Cable Club Server.
Contains the party validation logic and related functions.
"""

import configparser
import io
import os.path
import logging

from config import (
    POKEMON_MAX_NAME_SIZE, PLAYER_MAX_NAME_SIZE, MAXIMUM_LEVEL,
    IV_STAT_LIMIT, EV_LIMIT, EV_STAT_LIMIT, SKETCH_MOVE_IDS,
    ESSENTIALS_DELUXE_INSTALLED, MUI_MEMENTOS_INSTALLED,
    ZUD_DYNAMAX_INSTALLED, PLA_INSTALLED, TERA_INSTALLED, FOCUS_INSTALLED
)
from models import Pokemon, Universe


def make_party_validator(pbs_dir):
    """Create a party validation function based on PBS data files."""
    ability_syms = set()
    move_syms = set()
    item_syms = set()
    pokemon_by_name = {}

    # Load abilities
    with io.open(os.path.join(pbs_dir, r'abilities.txt'), 'r', encoding='utf-8-sig') as abilities_pbs:
        abilities_pbs_ = configparser.ConfigParser()
        abilities_pbs_.read_file(abilities_pbs)
        for internal_id in abilities_pbs_.sections():
            ability_syms.add(internal_id)

    # Load moves
    with io.open(os.path.join(pbs_dir, r'moves.txt'), 'r', encoding='utf-8-sig') as moves_pbs:
        moves_pbs_ = configparser.ConfigParser()
        moves_pbs_.read_file(moves_pbs)
        for internal_id in moves_pbs_.sections():
            move_syms.add(internal_id)

    # Load items
    with io.open(os.path.join(pbs_dir, r'items.txt'), 'r', encoding='utf-8-sig') as items_pbs:
        items_pbs_ = configparser.ConfigParser()
        items_pbs_.read_file(items_pbs)
        for internal_id in items_pbs_.sections():
            item_syms.add(internal_id)

    # Load Pokemon species data
    with io.open(os.path.join(pbs_dir, r'server_pokemon.txt'), 'r', encoding='utf-8-sig') as pokemon_pbs:
        pokemon_pbs_ = configparser.ConfigParser()
        pokemon_pbs_.read_file(pokemon_pbs)
        for section in pokemon_pbs_.sections():
            species = pokemon_pbs_[section]
            if 'forms' in species:
                forms = {int(f) for f in species['forms'].split(',') if f}
            else:
                forms = Universe()
            genders = {
                'AlwaysMale': {0},
                'AlwaysFemale': {1},
                'Genderless': {2},
            }.get(species['gender_ratio'], {0, 1})
            ability_names = species['abilities'].split(',')
            abilities = {a for a in ability_names if a}
            moves = {m for m in species['moves'].split(',') if m}
            pokemon_by_name[section] = Pokemon(genders, abilities, moves, forms)

    def validate_party(record):
        """Validate a party of Pokemon from a record."""
        errors = []
        try:
            for _ in range(record.int()):
                def validate_pokemon():
                    species = record.str()
                    species_ = pokemon_by_name.get(species)
                    if species_ is None:
                        logging.debug('invalid species: %s', species)
                        errors.append("invalid species")
                    logging.debug('Species: %s', species)
                    level = record.int()
                    if not (1 <= level <= MAXIMUM_LEVEL):
                        logging.debug('invalid level: %d', level)
                        errors.append("invalid level")
                    personal_id = record.int()
                    owner_id = record.int()
                    if owner_id & ~0xFFFFFFFF:
                        logging.debug('invalid owner id: %d', owner_id)
                        errors.append("invalid owner id")
                    owner_name = record.str()
                    if not (len(owner_name) <= PLAYER_MAX_NAME_SIZE):
                        logging.debug('invalid owner name: %s', owner_name)
                        errors.append("invalid owner name")
                    owner_gender = record.int()
                    if owner_gender not in {0, 1}:
                        logging.debug('invalid owner gender: %d', owner_gender)
                        errors.append("invalid owner gender")
                    exp = record.int()
                    # TODO: validate exp.
                    form = record.int()
                    if form not in species_.forms:
                        logging.debug('invalid form: %d', form)
                        errors.append("invalid form")
                    item = record.str()
                    if item and item not in item_syms:
                        logging.debug('invalid item: %s', item)
                        errors.append("invalid item")
                    can_use_sketch = not set(SKETCH_MOVE_IDS).isdisjoint(species_.moves)
                    
                    # Validate current moves
                    for _ in range(record.int()):
                        move = record.str()
                        if move:
                            if can_use_sketch and move not in move_syms:
                                logging.debug('invalid move id (Sketched): %s', move)
                                errors.append("invalid move (Sketched)")
                            elif move not in species_.moves and not can_use_sketch:
                                logging.debug('invalid move id: %s', move)
                                errors.append("invalid move")
                        ppup = record.int()
                        if not (0 <= ppup <= 3):
                            logging.debug('invalid ppup for move id %s: %d', move, ppup)
                            errors.append("invalid ppup")
                        if PLA_INSTALLED:
                            mastery = record.bool_or_none()
                    
                    # Validate first moves
                    for _ in range(record.int()):
                        move = record.str()
                        if move:
                            if can_use_sketch and move not in move_syms:
                                logging.debug('invalid first move id (Sketched): %s', move)
                                errors.append("invalid first move (Sketched)")
                            elif move not in species_.moves and not can_use_sketch:
                                logging.debug('invalid first move id: %s', move)
                                errors.append("invalid first move")
                    
                    # Validate mastered moves (PLA)
                    if PLA_INSTALLED:
                        for _ in range(record.int()):
                            move = record.str()
                            if move:
                                if can_use_sketch and move not in move_syms:
                                    logging.debug('invalid mastered move id (Sketched): %s', move)
                                    errors.append("invalid mastered move (Sketched)")
                                elif move not in species_.moves and not can_use_sketch:
                                    logging.debug('invalid mastered move id: %s', move)
                                    errors.append("invalid mastered move")
                    
                    gender = record.int()
                    if gender not in species_.genders:
                        logging.debug('invalid gender: %d', gender)
                        errors.append("invalid gender")
                    shiny = record.bool_or_none()
                    ability = record.str()
                    # stricter check
                    #if ability and ability not in species_.abilities):
                    #    logging.debug('invalid ability strict: %s', ability)
                    #    errors.append("invalid ability strict")
                    if ability and ability not in ability_syms:
                        logging.debug('invalid ability: %s', ability)
                        errors.append("invalid ability")
                    ability_index = record.int_or_none() # so hidden abils are properly inherited
                    nature_id = record.str()
                    nature_stats_id = record.str()
                    
                    # Validate IVs and EVs
                    ev_sum = 0
                    for _ in range(6):
                        iv = record.int()
                        if not (0 <= iv <= IV_STAT_LIMIT):
                            logging.debug('invalid IV: %d', iv)
                            errors.append("invalid IV")
                        ivmaxed = record.bool_or_none()
                        ev = record.int()
                        if not (0 <= ev <= EV_STAT_LIMIT):
                            logging.debug('invalid EV: %d', ev)
                            errors.append("invalid EV")
                        ev_sum += ev
                    if not (0 <= ev_sum <= EV_LIMIT):
                        logging.debug('invalid EV sum: %d', ev_sum)
                        errors.append("invalid EV sum")
                    
                    happiness = record.int()
                    if not (0 <= happiness <= 255):
                        logging.debug('invalid happiness: %d', happiness)
                        errors.append("invalid happiness")
                    name = record.str()
                    if not (len(name) <= POKEMON_MAX_NAME_SIZE):
                        logging.debug('invalid name: %s', name)
                        errors.append("invalid name")
                    poke_ball = record.str()
                    if poke_ball and poke_ball not in item_syms:
                        logging.debug('invalid pokeball: %s', poke_ball)
                        errors.append("invalid pokeball")
                    steps_to_hatch = record.int()
                    pokerus = record.int()
                    
                    # Obtain data
                    obtain_mode = record.int()
                    obtain_map = record.int()
                    obtain_text = record.str()
                    obtain_level = record.int()
                    hatched_map = record.int()
                    
                    # Contest stats
                    cool = record.int()
                    beauty = record.int()
                    cute = record.int()
                    smart = record.int()
                    tough = record.int()
                    sheen = record.int()
                    
                    # Ribbons
                    for _ in range(record.int()):
                        ribbon = record.str()
                    
                    # Essentials Deluxe Properties
                    if ESSENTIALS_DELUXE_INSTALLED or MUI_MEMENTOS_INSTALLED:
                        scale = record.int()
                    if MUI_MEMENTOS_INSTALLED:
                        memento = record.str()
                    if ZUD_DYNAMAX_INSTALLED:
                        dmax_level = record.int()
                        gmax_factor = record.bool()
                        dmax_able = record.bool()
                    if TERA_INSTALLED:
                        tera_type = record.str()
                    if FOCUS_INSTALLED:
                        focus_type = record.str()
                    
                    # Mail
                    if record.bool():
                        m_item = record.str()
                        m_msg = record.str()
                        m_sender = record.str()
                        m_species1 = record.int_or_none()
                        if m_species1:
                            #[species,gender,shininess,form,shadowness,is egg]
                            m_gender1 = record.int()
                            m_shiny1 = record.bool()
                            m_form1 = record.int()
                            m_shadow1 = record.bool()
                            m_egg1 = record.bool()
                        
                        m_species2 = record.int_or_none()
                        if m_species2:
                            #[species,gender,shininess,form,shadowness,is egg]
                            m_gender2 = record.int()
                            m_shiny2 = record.bool()
                            m_form2 = record.int()
                            m_shadow2 = record.bool()
                            m_egg2 = record.bool()
                        
                        m_species3 = record.int_or_none()
                        if m_species3:
                            #[species,gender,shininess,form,shadowness,is egg]
                            m_gender3 = record.int()
                            m_shiny3 = record.bool()
                            m_form3 = record.int()
                            m_shadow3 = record.bool()
                            m_egg3 = record.bool()
                    
                    # Fused Pokemon
                    if record.bool():
                        logging.debug('Fused Mon')
                        validate_pokemon()
                    logging.debug('-------')
                
                validate_pokemon()
            
            rest = record.raw_all()
            if rest:
                errors.append(f"remaining data: {', '.join(rest)}")
        except Exception as e:
            errors.append(str(e))
        
        if errors: 
            logging.debug('Errors: %s', errors)
        logging.debug('--END PARTY VALIDATION--')
        return not errors

    return validate_party