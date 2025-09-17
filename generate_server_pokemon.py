"""
Generator for server_pokemon.txt file.
Converts Pokemon PBS data to server format with suffix support.
"""

import os
import glob
import configparser
import io
from pathlib import Path
from typing import Dict, List, Set, Optional


# Configuration
SUFFIXES = ["absolution", "monarch"]
MODE = "shared"  # 'simple' | 'propagate' | 'shared'
PBS_DIR = "./PBS"


def expand_with_suffixes(dir_path: str, base_name: str, suffixes: List[str]) -> List[str]:
    """Expand a base filename with suffixes."""
    files = [os.path.join(dir_path, base_name)]
    for suffix in suffixes:
        files.append(os.path.join(dir_path, base_name.replace(".txt", f"_{suffix}.txt")))
    return files


def clean_pbs_except_moves_abilities_items():
    """Remove all PBS files except those containing 'moves', 'abilities' or 'items' in their name."""
    pbs_dir = os.path.abspath(PBS_DIR)
    if not os.path.exists(pbs_dir):
        return
    
    for file_path in glob.glob(os.path.join(pbs_dir, "*.txt")):
        file_name = os.path.basename(file_path)
        if not any(keyword in file_name for keyword in ['moves', 'abilities', 'items']):
            try:
                os.remove(file_path)
                print(f"Removed: {file_name}")
            except OSError as e:
                print(f"Error removing {file_name}: {e}")


def parse_pbs_file(filename: str) -> Dict[str, Dict[str, str]]:
    """Parse a PBS/INI file and return structured data."""
    data = {}
    current_section = None
    
    try:
        with io.open(filename, 'r', encoding='utf-8-sig') as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if line.startswith('[') and line.endswith(']'):
                    # Section header
                    current_section = line[1:-1]
                    data[current_section] = {}
                elif current_section and '=' in line:
                    # Key=value line
                    key, value = line.split('=', 1)
                    data[current_section][key.strip()] = value.strip()
    except FileNotFoundError:
        print(f"Warning: File not found: {filename}")
    except Exception as e:
        print(f"Error parsing {filename}: {e}")
    
    return data


def parse_pbs_files(filenames: List[str]) -> Dict[str, Dict[str, str]]:
    """Parse multiple PBS files and combine their data."""
    combined_data = {}
    
    for filename in filenames:
        if not os.path.exists(filename):
            continue
        
        file_data = parse_pbs_file(filename)
        
        # Merge data - later files override earlier ones
        for section, kv in file_data.items():
            if section not in combined_data:
                combined_data[section] = {}
            combined_data[section].update(kv)
    
    return combined_data


class EvolutionGraph:
    """Graph to track evolution relationships between Pokemon."""
    
    def __init__(self):
        self._graph = {}  # species -> set of (connected_species, is_child)
        self._base_mons = set()
    
    def add_evolution(self, prevo: str, evo: str):
        """Add an evolution relationship: prevo evolves into evo."""
        if prevo not in self._graph:
            self._graph[prevo] = set()
        if evo not in self._graph:
            self._graph[evo] = set()
        
        self._graph[prevo].add((evo, False))  # prevo -> evo
        self._graph[evo].add((prevo, True))   # evo <- prevo
        
        self._base_mons.add(prevo)
        # If prevo is an evolution of someone else, remove it from base
        if any(is_child for _, is_child in self._graph[prevo]):
            self._base_mons.discard(prevo)
    
    def get_directly_connected_mons(self, base: str) -> Set[str]:
        """Get all Pokemon that base evolves into."""
        if base not in self._graph:
            return set()
        return {conn for conn, is_child in self._graph[base] if not is_child}
    
    def depth_first_search(self, start: str) -> List[str]:
        """Get all Pokemon in the evolution family starting from start."""
        seen = set()
        stack = [start]
        result = []
        
        while stack:
            current = stack.pop()
            if current in seen or not current:
                continue
            
            seen.add(current)
            result.append(current)
            
            if current in self._graph:
                for conn, is_child in self._graph[current]:
                    if not is_child:  # Only follow evolution paths, not pre-evolutions
                        stack.append(conn)
        
        return result
    
    def flatten_families(self, mode: str) -> Dict[str, Set[str]]:
        """Get evolution families based on mode."""
        families = {}
        
        if mode == "shared":
            for base in self._base_mons:
                families[base] = set(self.depth_first_search(base))
        elif mode == "propagate":
            for base in self._base_mons:
                families[base] = self.get_directly_connected_mons(base)
            
            # Include non-base Pokemon with their connections
            non_bases = set(self._graph.keys()) - self._base_mons
            for mon in non_bases:
                families[mon] = self.get_directly_connected_mons(mon)
        
        # Remove empty entries
        families = {k: v for k, v in families.items() if k and v}
        return families


def organize_evo_families(input_files: List[str], forms_files: List[str]) -> EvolutionGraph:
    """Organize evolution families from PBS data."""
    evos = EvolutionGraph()
    
    # Parse main PBS data
    base_data = parse_pbs_files(input_files)
    
    for section, kv in base_data.items():
        internal_name = kv.get("InternalName", section)
        evolutions = kv.get("Evolutions", "")
        
        if evolutions:
            evo_data = evolutions.split(",")
            # Every 3 items: mon, method, level/param
            for i in range(0, len(evo_data), 3):
                if i < len(evo_data):
                    mon = evo_data[i].strip()
                    if mon:
                        evos.add_evolution(internal_name, mon)
    
    # Parse forms data
    if forms_files:
        forms_data = parse_pbs_files(forms_files)
        
        for section, kv in forms_data.items():
            # Handle sections like "PIKACHU, 1"
            section_key = section.replace(",", "-").replace(" ", "-")
            internal_name = section_key.split("-")[0]
            
            evolutions = kv.get("Evolutions", "")
            if evolutions:
                evo_data = evolutions.split(",")
                for i in range(0, len(evo_data), 3):
                    if i < len(evo_data):
                        mon = evo_data[i].strip()
                        if mon:
                            evos.add_evolution(internal_name, mon)
    
    return evos


def generate_server_pokemon_pbs(
    mode: str,
    input_files: List[str],
    output_file: str,
    forms_files: Optional[List[str]] = None,
    tm_files: Optional[List[str]] = None
):
    """Generate server_pokemon.txt from PBS data."""
    
    # Build evolution families if needed
    evo_fams = None
    if mode in ["propagate", "shared"]:
        evo_fams = organize_evo_families(input_files, forms_files or [])
    
    # Parse main input PBS
    pbs_data = parse_pbs_files(input_files)
    
    output_data = {}
    
    # Process main Pokemon data
    for section, species in pbs_data.items():
        internal_name = species.get("InternalName", section)
        output_data[internal_name] = {
            "internal_number": section,
            "forms": "0"
        }
        
        # Gender ratio
        gender_ratio = (species.get("GenderRate") or 
                       species.get("GenderRatio") or 
                       "Female50Percent")
        output_data[internal_name]["gender_ratio"] = gender_ratio
        
        # Abilities
        all_abilities = set()
        if species.get("Abilities"):
            all_abilities.update(a.strip() for a in species["Abilities"].split(","))
        if species.get("HiddenAbility"):
            all_abilities.update(a.strip() for a in species["HiddenAbility"].split(","))
        if species.get("HiddenAbilities"):
            all_abilities.update(a.strip() for a in species["HiddenAbilities"].split(","))
        
        all_abilities.discard("")  # Remove empty strings
        output_data[internal_name]["abilities"] = ",".join(sorted(all_abilities))
        
        # Moves
        moves_set = set()
        if species.get("Moves"):
            moves_array = species["Moves"].split(",")
            # Every 2nd entry is a move (level, move, level, move, ...)
            for i in range(1, len(moves_array), 2):
                move = moves_array[i].strip()
                if move:
                    moves_set.add(move)
        
        if species.get("EggMoves"):
            moves_set.update(m.strip() for m in species["EggMoves"].split(","))
        if species.get("TutorMoves"):
            moves_set.update(m.strip() for m in species["TutorMoves"].split(","))
        
        moves_set.discard("")  # Remove empty strings
        output_data[internal_name]["moves"] = ",".join(sorted(moves_set))
    
    # Process forms data
    if forms_files:
        forms_data = parse_pbs_files(forms_files)
        
        for section, kv in forms_data.items():
            section_key = section.replace(",", "-").replace(" ", "-")
            parts = section_key.split("-")
            base_name = parts[0]
            form_number = parts[1] if len(parts) > 1 else ""
            
            if base_name not in output_data:
                continue
            
            # Add form number
            if form_number and form_number.strip():
                forms_str = output_data[base_name]["forms"]
                forms_list = forms_str.split(",") if forms_str else []
                if form_number not in forms_list:
                    forms_list.append(form_number)
                output_data[base_name]["forms"] = ",".join(forms_list)
            
            # Merge abilities
            existing_abilities = set(output_data[base_name]["abilities"].split(","))
            existing_abilities.discard("")
            
            if kv.get("Abilities"):
                existing_abilities.update(a.strip() for a in kv["Abilities"].split(","))
            if kv.get("HiddenAbility"):
                existing_abilities.update(a.strip() for a in kv["HiddenAbility"].split(","))
            if kv.get("HiddenAbilities"):
                existing_abilities.update(a.strip() for a in kv["HiddenAbilities"].split(","))
            
            existing_abilities.discard("")
            output_data[base_name]["abilities"] = ",".join(sorted(existing_abilities))
            
            # Merge moves
            existing_moves = set(output_data[base_name]["moves"].split(","))
            existing_moves.discard("")
            
            if kv.get("Moves"):
                moves_array = kv["Moves"].split(",")
                for i in range(1, len(moves_array), 2):
                    move = moves_array[i].strip()
                    if move:
                        existing_moves.add(move)
            
            if kv.get("EggMoves"):
                existing_moves.update(m.strip() for m in kv["EggMoves"].split(","))
            if kv.get("TutorMoves"):
                existing_moves.update(m.strip() for m in kv["TutorMoves"].split(","))
            
            existing_moves.discard("")
            output_data[base_name]["moves"] = ",".join(sorted(existing_moves))
    
    # Process TM files
    if tm_files:
        current_move = None
        for tm_file in tm_files:
            if not os.path.exists(tm_file):
                continue
            
            try:
                with io.open(tm_file, 'r', encoding='utf-8-sig') as file:
                    for line in file:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        
                        if line.startswith('[') and line.endswith(']'):
                            current_move = line[1:-1]
                        elif current_move:
                            for name in line.split(","):
                                name = name.strip()
                                if not name:
                                    continue
                                
                                base_name = name.split("_")[0]  # Handle variants like BULBASAUR_Alolan
                                if base_name in output_data:
                                    existing_moves = set(output_data[base_name]["moves"].split(","))
                                    existing_moves.discard("")
                                    existing_moves.add(current_move)
                                    output_data[base_name]["moves"] = ",".join(sorted(existing_moves))
            except Exception as e:
                print(f"Error processing TM file {tm_file}: {e}")
    
    # Apply evolution family logic
    if evo_fams:
        families = evo_fams.flatten_families(mode)
        
        for base, family_set in families.items():
            if mode == "propagate":
                # Don't include base in its own propagation
                family_set.discard(base)
                if base in output_data:
                    base_moves = set(output_data[base]["moves"].split(","))
                    base_moves.discard("")
                    
                    # Add base's moves to all family members
                    for mon in family_set:
                        if mon in output_data:
                            mon_moves = set(output_data[mon]["moves"].split(","))
                            mon_moves.discard("")
                            mon_moves.update(base_moves)
                            output_data[mon]["moves"] = ",".join(sorted(mon_moves))
            
            elif mode == "shared":
                # Combine moves from entire family
                combined_moves = set()
                for mon in family_set:
                    if mon in output_data:
                        mon_moves = set(output_data[mon]["moves"].split(","))
                        mon_moves.discard("")
                        combined_moves.update(mon_moves)
                
                # Assign combined moves to all family members
                for mon in family_set:
                    if mon in output_data:
                        output_data[mon]["moves"] = ",".join(sorted(combined_moves))
    
    # Write output file
    with io.open(output_file, 'w', encoding='utf-8') as f:
        for section, kv in output_data.items():
            f.write(f"[{section}]\n")
            for key, value in kv.items():
                f.write(f"{key}={value}\n")
            f.write("\n")
    
    print(f"Generated {output_file} with {len(output_data)} Pokemon entries.")


def main():
    """Main function to generate server_pokemon.txt."""
    # Define file lists with suffixes
    input_files = expand_with_suffixes(PBS_DIR, "pokemon.txt", SUFFIXES)
    forms_files = expand_with_suffixes(PBS_DIR, "pokemon_forms.txt", SUFFIXES)
    tm_files = expand_with_suffixes(PBS_DIR, "tm.txt", SUFFIXES)
    
    output_file = "PBS/server_pokemon.txt"
    
    # Clean PBS directory
    print("Cleaning PBS directory...")
    clean_pbs_except_moves_abilities_items()
    
    # Generate server pokemon file
    print("Generating server_pokemon.txt...")
    generate_server_pokemon_pbs(
        mode=MODE,
        input_files=input_files,
        output_file=output_file,
        forms_files=forms_files,
        tm_files=tm_files
    )
    
    print("Done!")


if __name__ == "__main__":
    main()