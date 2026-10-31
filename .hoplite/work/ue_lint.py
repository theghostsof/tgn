#!/usr/bin/env python3
"""Static checks for UE compile pitfalls the standalone logic build cannot catch."""
import pathlib
import re
import sys
from collections import defaultdict

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
SRC = ROOT / "Plugins/GhostsOfNovember/Source"
issues = []

def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)

# Engine members that are easy to shadow inside actor/component/controller/widget methods.
ENGINE_MEMBERS = {
    "Owner", "Tags", "Instigator", "RootComponent", "Children", "Controller", "PlayerState",
    "Mesh", "CapsuleComponent", "CharacterMovement", "Velocity", "Bounds", "Mobility", "Pawn",
    "Blackboard", "BrainComponent", "PathFollowingComponent", "PerceptionComponent",
    "PlayerOwner", "Visibility", "InputComponent", "ComponentTags", "AttachParent",
    "PrimaryActorTick", "PrimaryComponentTick", "Layers", "NetDriverName", "UpdatedComponent",
    "MovementMode", "CustomMovementMode", "Acceleration", "PlayerCameraManager", "MyHUD",
    "AttachChildren", "RelativeLocation", "RelativeRotation", "RelativeScale3D", "ComponentVelocity",
    "BodyInstance", "OverrideMaterials", "StaticMesh", "SkeletalMesh", "Intensity", "LightColor",
    "AttenuationRadius", "OuterConeAngle", "InnerConeAngle", "Sound", "VolumeMultiplier", "PitchMultiplier",
    "DebugCanvas", "WebBrowserWidget",
    "AIControllerClass", "AutoPossessAI", "BaseEyeHeight", "JumpMaxCount", "GravityScale", "MaxWalkSpeed",
}
CLASS_BASES_WITH_MEMBERS = re.compile(r"class\s+\w+_API\s+(\w+)\s*(?:final\s*)?:\s*public\s+(A\w+|U\w+Component|U\w+Widget|UWebBrowser|AAIController|AHUD|U\w+Subsystem)")

headers = list(SRC.rglob("*.h"))
cpps = list(SRC.rglob("*.cpp"))
module_of = lambda p: p.relative_to(SRC).parts[0]

_texts = {}
def used_elsewhere(symbol, module):
    for f in cpps + headers:
        if module_of(f) == module:
            continue
        if f not in _texts:
            _texts[f] = strip_comments(f.read_text(encoding="utf-8"))
        if re.search(r"\b" + re.escape(symbol) + r"\b", _texts[f]):
            return True
    return False

# 1) _API on Public/Logic non-inline functions and structs/classes with out-of-line methods.
for h in headers:
    rel = h.relative_to(SRC)
    if len(rel.parts) < 3 or rel.parts[1] != "Public" or rel.parts[2] != "Logic":
        continue
    macro = module_of(h).upper() + "_API"
    raw = h.read_text(encoding="utf-8")
    text = strip_comments(raw)
    uses_macro = macro in text
    has_fallback = f"#ifndef {macro}" in text
    # Function declarations ending with ';' at namespace scope (heuristic: lines indented with one tab inside namespace).
    decls = re.findall(r"^\t([A-Za-z_][\w:<>,\s\*&]*?\s[\*&]?([A-Z]\w*)\s*\([^;{]*\)\s*(?:const)?\s*;)", text, re.M)
    for full, name in decls:
        if "inline" in full or "static" in full or "virtual" in full or "constexpr" in full or "template" in full:
            continue
        if macro not in full and not re.match(r"^\s*(?:using|typedef|return)", full) and used_elsewhere(name, module_of(h)):
            issues.append(f"[api] {rel}: '{name}' declared without {macro} and used from another module")
    # Classes/structs with declared-but-not-defined member functions.
    for m in re.finditer(r"^\t(struct|class)\s+(\w+_API\s+)?(\w+)[^;{]*\{", text, re.M):
        start = m.end()
        depth, i = 1, start
        while i < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        body = text[start:i - 1]
        # remove nested braces bodies
        flat = re.sub(r"\{[^{}]*\}", "{}", body)
        flat = re.sub(r"\{[^{}]*\}", "{}", flat)
        outofline = re.findall(r"^\s*(?!virtual\b)(?!static\b)(?!inline\b)(?!friend\b)[\w:<>,\*&\s]+?\b(\w+)\s*\([^;{}]*\)\s*(?:const)?\s*(?:override)?\s*;", flat, re.M)
        outofline = [n for n in outofline if n not in ("operator",)]
        if outofline and not m.group(2) and m.group(1) in ("struct", "class"):
            if not re.search(r"=\s*0\s*;", flat) or len(outofline) > 0:
                # pure-virtual-only interfaces are fine
                pv = re.findall(r"virtual[^;]*=\s*0\s*;", flat)
                if len(outofline) > 0 and used_elsewhere(m.group(3), module_of(h)):
                    issues.append(f"[api] {rel}: {m.group(1)} {m.group(3)} has out-of-line members {outofline[:3]} but no {macro}")
    if uses_macro and not has_fallback:
        issues.append(f"[api] {rel}: uses {macro} without '#ifndef {macro}' fallback")

# 2) UHT rules in headers.
for h in headers:
    rel = h.relative_to(SRC)
    text = h.read_text(encoding="utf-8")
    code = strip_comments(text)
    if re.search(r"\b(UCLASS|USTRUCT|UENUM|UINTERFACE)\s*\(", code):
        incs = re.findall(r'^#include\s+"([^"]+)"', code, re.M)
        if not incs or not incs[-1].endswith(".generated.h"):
            issues.append(f"[uht] {rel}: .generated.h is not the last include")
        elif incs[-1] != h.stem + ".generated.h":
            issues.append(f"[uht] {rel}: generated include name {incs[-1]} != {h.stem}.generated.h")
    for m in re.finditer(r"UPROPERTY\([^)]*\)\s*\n?\s*([^;]+);", code):
        decl = m.group(1)
        if re.match(r"\s*(unsigned\s+)?(int|long|short|unsigned|size_t|std::)\b", decl):
            issues.append(f"[uht] {rel}: UPROPERTY with non-UHT type: {decl.strip()[:80]}")
        if re.search(r"\b[A-Z]\w*\s*\*\s*\w+\s*(=|$)", decl) and "TObjectPtr" not in decl and "class " not in decl:
            issues.append(f"[uht] {rel}: raw object pointer UPROPERTY (use TObjectPtr): {decl.strip()[:80]}")
        if "GoN::" in decl:
            issues.append(f"[uht] {rel}: UPROPERTY with pure namespaced type: {decl.strip()[:80]}")
    # forward declarations inside UCLASS bodies
    for m in re.finditer(r"\bUCLASS\([^)]*\)\s*class[^{]*\{", code):
        start = m.end(); depth, i = 1, start
        while i < len(code) and depth:
            depth += {"{": 1, "}": -1}.get(code[i], 0); i += 1
        body = code[start:i]
        for fd in re.findall(r"^\s*(?:class|struct)\s+\w+\s*;", body, re.M):
            issues.append(f"[fwd] {rel}: forward declaration inside UCLASS body: {fd.strip()}")
    for m in re.finditer(r"UFUNCTION\([^)]*\)\s*\n?\s*([^;{]+)", code):
        if "std::" in m.group(1) or "GoN::" in m.group(1):
            issues.append(f"[uht] {rel}: UFUNCTION with non-UHT type: {m.group(1).strip()[:90]}")

# 3) Unity build collisions per module: anonymous namespaces, duplicate Detail namespaces across files,
#    duplicate file-scope console variable names, duplicate logic test ids.
per_module = defaultdict(list)
for c in cpps:
    per_module[module_of(c)].append(c)
for module, files in per_module.items():
    names = defaultdict(list)
    test_ids = defaultdict(list)
    for f in files:
        code = strip_comments(f.read_text(encoding="utf-8"))
        if re.search(r"^\s*namespace\s*\{", code, re.M):
            issues.append(f"[unity] {f.relative_to(SRC)}: anonymous namespace (unity collisions)")
        for n in re.findall(r"^\s*namespace\s+(\w+Detail)\b", code, re.M):
            names[("ns", n)].append(f)
        for n in re.findall(r"^(?:static\s+)?(?:TAutoConsoleVariable<[^>]+>|FAutoConsoleCommand\w*|FAutoConsoleVariableRef)\s+(\w+)", code, re.M):
            names[("cvar", n)].append(f)
        for n in re.findall(r"^static\s+[\w:<>]+\s+(\w+)\s*\(", code, re.M):
            names[("static", n)].append(f)
        for n in re.findall(r"GON_LOGIC_TEST\(\s*\"[^\"]+\"\s*,\s*(\w+)\s*\)", code):
            test_ids[n].append(f)
    for (kind, n), fs in names.items():
        uniq = sorted(set(fs))
        if len(uniq) > 1 and kind != "ns":
            issues.append(f"[unity] {module}: {kind} '{n}' defined in {[str(x.name) for x in uniq]}")
        if kind == "ns" and len(uniq) > 1:
            # same Detail namespace reopened in several files is legal, but helpers with the same name would clash; flag as note
            pass
    for n, fs in test_ids.items():
        if len(fs) > 1:
            issues.append(f"[unity] {module}: test id {n} used {len(fs)} times")

# 4) Shadowing heuristics: locals/params named like engine members inside classes deriving from engine types.
class_files = {}
for h in headers:
    code = strip_comments(h.read_text(encoding="utf-8"))
    for m in CLASS_BASES_WITH_MEMBERS.finditer(code):
        members = set(re.findall(r"^\s*(?:UPROPERTY\([^)]*\)\s*)?(?:TObjectPtr<\w+>|[\w:<>,\* ]+?)\s+\b(\w+)\s*(?:=[^;]*)?;", code, re.M))
        class_files[m.group(1)] = (h, members)
for c in cpps:
    code = strip_comments(c.read_text(encoding="utf-8"))
    for m in re.finditer(r"^[\w:<>\*& ]*?\b(\w+)::(\w+)\s*\(([^)]*)\)\s*(?:const)?\s*\{", code, re.M):
        cls = m.group(1)
        if cls not in class_files:
            continue
        own_members = class_files[cls][1]
        start = m.end(); depth, i = 1, start
        while i < len(code) and depth:
            depth += {"{": 1, "}": -1}.get(code[i], 0); i += 1
        body = code[start:i]
        params = re.findall(r"\b(\w+)\s*(?:=[^,]*)?(?:,|$)", m.group(3))
        locals_ = re.findall(r"(?:^|[;{(]\s*)(?:const\s+)?(?:auto|[A-Z]\w*(?:<[^;=()]*>)?|float|double|int32|bool|uint8|int|FVector|FRotator)\s*[\*&]*\s+(\w+)\s*(?:=|;|\(|\{|:)", body, re.M)
        lambda_params = re.findall(r"\]\s*\(([^)]*)\)", body)
        lp = []
        for group in lambda_params:
            lp += re.findall(r"\b(\w+)\s*(?:,|$)", group)
        for name in set(params + locals_ + lp):
            if name in ENGINE_MEMBERS or name in own_members:
                issues.append(f"[shadow?] {c.relative_to(SRC)}: {cls}::{m.group(2)} declares '{name}'")

for line in sorted(set(issues)):
    print(line)
print(f"{len(set(issues))} issue(s)")
